import json
import src.agent.models as models
import src.agent.repository as repository
import src.agent.tools as tools
from src.agent.utils import get_mimo_cost
from typing import AsyncGenerator
from openai import OpenAI
import os

client = OpenAI(
    base_url="https://api.xiaomimimo.com/v1", api_key=os.getenv("MIMO_API_KEY")
)

MAX_TURNS = 35
MODEL_ID = "mimo-v2.5"

TOOL_DECLARATIONS = [
    tools.search_declaration,
    tools.fetch_declaration,
    tools.search_foods_declaration,
    tools.get_all_foods_declaration,
    tools.get_food_by_id_declaration,
    tools.insert_food_declaration,
    tools.update_food_declaration,
    tools.delete_food_declaration,
    tools.get_serving_sizes_by_food_id_declaration,
    tools.insert_serving_size_declaration,
    tools.update_serving_size_declaration,
    tools.delete_serving_size_declaration,
    tools.get_daily_summary_declaration,
    tools.insert_food_log_by_grams_declaration,
    tools.insert_food_log_by_serving_size_declaration,
    tools.update_food_log_declaration,
    tools.delete_food_log_declaration,
    tools.get_current_goal_declaration,
    tools.insert_goal_declaration,
    tools.get_latest_measurements_declaration,
    tools.insert_measurement_declaration,
]


def _to_openai_tools(declarations: list) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": d.name,
                "description": d.description,
                "parameters": d.parameters_json_schema,
            },
        }
        for d in declarations
    ]


async def _invoke_model(
    model_id: str,
    messages: list[dict],
) -> tuple[dict, dict]:
    for _ in range(3):
        try:
            response = client.chat.completions.create(
                model=model_id,
                messages=messages,
                extra_body={"thinking": {"type": "disabled"}},
                tools=_to_openai_tools(TOOL_DECLARATIONS),
                max_completion_tokens=1024,
                temperature=1.0,
                top_p=0.95,
            )
            print(f"Model response:\n{response}")
            message = response.choices[0].message
            usage = response.usage.model_dump() if response.usage else {}
            return message.model_dump(), usage
        except Exception as e:
            print(f"Model exception: {e}")
    raise Exception("Failed to invoke model after 3 attempts.")


def _convert_history(contents: list[dict]) -> list[dict]:
    messages: list[dict] = []
    for msg in contents:
        role = msg.get("role")
        if role in ("user", "model"):
            content = msg.get("content")
            if isinstance(content, (str, list)):
                messages.append(
                    {
                        "role": "user" if role == "user" else "assistant",
                        "content": content,
                    }
                )
            elif "parts" in msg:
                text_parts = []
                for part in msg["parts"]:
                    if isinstance(part, dict) and part.get("text"):
                        text_parts.append(part["text"])
                if text_parts:
                    openai_role = "user" if role == "user" else "assistant"
                    messages.append(
                        {"role": openai_role, "content": "\n".join(text_parts)}
                    )
            continue
        if role == "assistant":
            messages.append(msg)
            continue
        if role == "tool":
            messages.append(msg)
    return messages


def _get_tool_response(tool_call: dict, user_id: str) -> dict:
    args = json.loads(tool_call["function"]["arguments"])
    name = tool_call["function"]["name"]
    response = None
    try:
        match name:
            case "search":
                response = {"results": tools.search_tool(**args)}
            case "fetch":
                response = {"results": tools.fetch_tool(**args)}
            case "search_foods":
                response = {"foods": tools.search_foods_tool(user_id=user_id, **args)}
            case "get_all_foods":
                response = {"foods": tools.get_all_foods_tool(user_id=user_id)}
            case "get_food_by_id":
                response = {
                    "food": tools.get_food_by_id_tool(
                        user_id=user_id, food_id=args["food_id"]
                    )
                }
            case "insert_food":
                response = {"food": tools.insert_food_tool(user_id=user_id, **args)}
            case "update_food":
                tools.update_food_tool(user_id=user_id, **args)
                response = {"success": True}
            case "delete_food":
                tools.delete_food_tool(user_id=user_id, food_id=args["food_id"])
                response = {"success": True}
            case "get_serving_sizes_by_food_id":
                response = {
                    "serving_sizes": tools.get_serving_sizes_by_food_id_tool(
                        user_id=user_id, food_id=args["food_id"]
                    )
                }
            case "insert_serving_size":
                response = {
                    "serving_size": tools.insert_serving_size_tool(
                        user_id=user_id, **args
                    )
                }
            case "update_serving_size":
                response = {
                    "serving_size": tools.update_serving_size_tool(
                        user_id=user_id, **args
                    )
                }
            case "delete_serving_size":
                tools.delete_serving_size_tool(
                    user_id=user_id, serving_size_id=args["serving_size_id"]
                )
                response = {"success": True}
            case "get_daily_summary":
                response = tools.get_daily_summary_tool(
                    user_id=user_id, day=args["day"]
                )
            case "insert_food_log_by_grams":
                tools.insert_food_log_by_grams_tool(user_id=user_id, **args)
                response = {"success": True}
            case "insert_food_log_by_serving_size":
                tools.insert_food_log_by_serving_size_tool(user_id=user_id, **args)
                response = {"success": True}
            case "update_food_log":
                tools.update_food_log_tool(user_id=user_id, **args)
                response = {"success": True}
            case "delete_food_log":
                tools.delete_food_log_tool(
                    user_id=user_id, food_log_id=args["food_log_id"]
                )
                response = {"success": True}
            case "get_current_goal":
                response = {"goal": tools.get_current_goal_tool(user_id=user_id)}
            case "insert_goal":
                tools.insert_goal_tool(user_id=user_id, **args)
                response = {"success": True}
            case "get_latest_measurements":
                response = {
                    "latest_measurement": tools.get_latest_measurements_tool(
                        user_id=user_id
                    )
                }
            case "insert_measurement":
                tools.insert_measurement_tool(user_id=user_id, **args)
                response = {"success": True}
    except Exception as e:
        response = {"error": str(e)}
    return {
        "tool_call_id": tool_call["id"],
        "role": "tool",
        "content": json.dumps(response),
    }


async def agent(
    input: models.AgentInput,
) -> AsyncGenerator[dict, None]:
    messages: list[dict] = [
        {"role": "system", "content": input.system_prompt},
        *_convert_history(input.contents),
    ]
    for _ in range(MAX_TURNS):
        message_dict, usage = await _invoke_model(MODEL_ID, messages)
        if usage:
            cost = get_mimo_cost(model_id=MODEL_ID, usage=usage)
            repository.insert_llm_invocation(
                total_cost=cost,
                raw_usage_metadata=usage,
                user_id=input.user_id,
                conversation_id=input.conversation_id,
            )
        messages.append(message_dict)
        yield message_dict
        tool_calls = message_dict.get("tool_calls") or []
        if not tool_calls:
            return
        for tc in tool_calls:
            tool_result = _get_tool_response(tc, input.user_id)
            messages.append(tool_result)
            yield tool_result
    raise Exception("Maximum number of turns reached without reaching a conclusion.")
