import src.agent.models as models
import src.agent.repository as repository
import src.agent.tools as tools
from src.agent.utils import get_google_genai_cost
from typing import AsyncGenerator
from google.genai import Client

client = Client()

MAX_TURNS = 35
MODEL_ID = "gemini-3.1-flash-lite"


async def _invoke_model(
    model_id: str,
    system_prompt: str,
    contents: list[models.Content],
) -> models.GenerateContentResponse:
    for _ in range(3):
        try:
            response = await client.aio.models.generate_content(
                model=model_id,
                contents=contents,
                config=models.GenerateContentConfig(
                    system_instruction=system_prompt,
                    thinking_config=models.ThinkingConfig(
                        include_thoughts=False,
                        thinking_level=models.ThinkingLevel.MINIMAL,
                    ),
                    tools=[
                        models.Tool(
                            function_declarations=[
                                tools.search_declaration,
                                tools.fetch_declaration,
                                tools.search_foods_declaration,
                                tools.get_all_foods_declaration,
                                tools.get_food_by_id_declaration,
                                tools.insert_food_declaration,
                                tools.update_food_declaration,
                                tools.delete_food_declaration,
                                tools.get_daily_summary_declaration,
                                tools.insert_food_log_declaration,
                                tools.update_food_log_declaration,
                                tools.delete_food_log_declaration,
                                tools.get_current_goal_declaration,
                                tools.insert_goal_declaration,
                                tools.get_latest_measurements_declaration,
                                tools.insert_measurement_declaration,
                            ],
                        )
                    ],
                ),
            )
            return response
        except Exception as e:
            pass
    raise Exception("Failed to invoke model after 3 attempts.")


def _get_tool_response(tool_call: models.FunctionCall) -> models.FunctionResponse:
    if tool_call.args is None:
        raise Exception("Tool call arguments are missing.")
    response = None
    try:
        match (tool_call.name):
            case "search":
                response = {"results": tools.search_tool(**tool_call.args)}
            case "fetch":
                response = {"results": tools.fetch_tool(**tool_call.args)}
            case "search_foods":
                response = {"foods": tools.search_foods_tool(**tool_call.args)}
            case "get_all_foods":
                response = {"foods": tools.get_all_foods_tool()}
            case "get_food_by_id":
                response = {
                    "food": tools.get_food_by_id_tool(tool_call.args["food_id"])
                }
            case "insert_food":
                response = {"food_id": tools.insert_food_tool(**tool_call.args)}
            case "update_food":
                tools.update_food_tool(**tool_call.args)
                response = {"success": True}
            case "delete_food":
                tools.delete_food_tool(tool_call.args["food_id"])
                response = {"success": True}
            case "get_daily_summary":
                response = tools.get_daily_summary_tool(tool_call.args["day"])
            case "insert_food_log":
                tools.insert_food_log_tool(**tool_call.args)
                response = {"success": True}
            case "update_food_log":
                tools.update_food_log_tool(**tool_call.args)
                response = {"success": True}
            case "delete_food_log":
                tools.delete_food_log_tool(tool_call.args["food_log_id"])
                response = {"success": True}
            case "get_current_goal":
                response = {"goal": tools.get_current_goal_tool()}
            case "insert_goal":
                tools.insert_goal_tool(**tool_call.args)
                response = {"success": True}
            case "get_latest_measurements":
                response = {"latest_measurement": tools.get_latest_measurements_tool()}
            case "insert_measurement":
                tools.insert_measurement_tool(**tool_call.args)
                response = {"success": True}
    except Exception as e:
        response = {"error": str(e)}
    return models.FunctionResponse(
        id=tool_call.id,
        name=tool_call.name,
        response=response,
    )


async def agent(
    input: models.AgentInput,
) -> AsyncGenerator[models.Content, None]:
    contents = input.contents
    for _ in range(MAX_TURNS):
        response = await _invoke_model(MODEL_ID, input.system_prompt, contents)
        if response.usage_metadata:
            cost = get_google_genai_cost(
                model_id=MODEL_ID,
                usage_metadata=response.usage_metadata,
            )
            repository.insert_llm_invocation(
                total_cost=cost,
                raw_usage_metadata=response.usage_metadata.model_dump(),
                conversation_id=input.conversation_id,
            )
        content = response.candidates[0].content if response.candidates else None
        if content is None:
            raise Exception("No content generated by the model.")
        parts = content.parts
        if not parts:
            raise Exception("Generated content has no parts.")
        contents.append(content)
        yield content
        has_any_tool_call = any(
            part.function_call for part in parts if part.function_call
        )
        if not has_any_tool_call:
            return
        tool_results = []
        for part in parts:
            if part.function_call:
                tool_response = _get_tool_response(part.function_call)
                tool_results.append(tool_response)
        tool_content = models.Content(
            role="user",
            parts=[
                models.Part(
                    function_response=tool_response,
                )
                for tool_response in tool_results
            ],
        )
        contents.append(tool_content)
        yield tool_content
    raise Exception("Maximum number of turns reached without reaching a conclusion.")
