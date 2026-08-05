import json
import src.agent.models as models
import src.agent.providers as providers
import src.agent.repository as repository
import src.agent.tools as tools
from src.agent.utils import extract_tokens, get_mimo_cost, get_openrouter_cost, inline_image_url
from typing import AsyncGenerator

MAX_TURNS = 35


def _sanitize_tool_calls(messages: list[dict]) -> None:
    """Validate and fix malformed tool call arguments in-place."""
    for msg in messages:
        if msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                args_str = tc.get("function", {}).get("arguments", "")
                if args_str:
                    try:
                        json.loads(args_str)
                    except json.JSONDecodeError:
                        tc["function"]["arguments"] = "{}"


TOOL_DECLARATIONS = [
    tools.search_declaration,
    tools.web_search_declaration,
    tools.web_fetch_declaration,
    tools.get_ingredient_by_id_declaration,
    tools.insert_ingredient_declaration,
    tools.update_ingredient_declaration,
    tools.delete_ingredient_declaration,
    tools.get_serving_sizes_by_ingredient_id_declaration,
    tools.insert_serving_size_declaration,
    tools.update_serving_size_declaration,
    tools.delete_serving_size_declaration,
    tools.get_recipe_by_id_declaration,
    tools.insert_recipe_declaration,
    tools.update_recipe_declaration,
    tools.delete_recipe_declaration,
    tools.get_daily_summary_declaration,
    tools.insert_log_by_grams_declaration,
    tools.insert_log_by_serving_size_declaration,
    tools.update_log_declaration,
    tools.delete_log_declaration,
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
) -> AsyncGenerator[dict | models.ContentTokenStep | models.ToolCallStartStep, None]:
    """Stream model response, yielding content tokens, tool call starts, and the final message dict."""
    provider = providers.get_provider(model_id)
    client = providers.get_client(provider)
    create_kwargs: dict = dict(
        model=model_id,
        messages=messages,
        tools=_to_openai_tools(TOOL_DECLARATIONS),
        max_completion_tokens=1024,
        temperature=1.0,
        top_p=0.95,
        stream=True,
    )
    if providers.PROVIDERS[provider]["supports_thinking_extension"]:
        create_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
    for _ in range(3):
        try:
            stream = await client.chat.completions.create(**create_kwargs)
            content_parts: list[str] = []
            tool_calls_acc: dict[int, dict] = {}
            tool_names_emitted: set[int] = set()
            usage = {}

            async for chunk in stream:
                choice = chunk.choices[0] if chunk.choices else None
                if choice:
                    delta = choice.delta
                    if delta.content:
                        content_parts.append(delta.content)
                        yield models.ContentTokenStep(token=delta.content)
                    if delta.tool_calls:
                        for tc_delta in delta.tool_calls:
                            idx = tc_delta.index
                            if idx not in tool_calls_acc:
                                tool_calls_acc[idx] = {
                                    "id": tc_delta.id or "",
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""},
                                }
                            if tc_delta.id:
                                tool_calls_acc[idx]["id"] = tc_delta.id
                            if tc_delta.function:
                                if tc_delta.function.name:
                                    tool_calls_acc[idx]["function"][
                                        "name"
                                    ] = tc_delta.function.name
                                    if idx not in tool_names_emitted:
                                        tool_names_emitted.add(idx)
                                        yield models.ToolCallStartStep(
                                            name=tc_delta.function.name
                                        )
                                if tc_delta.function.arguments:
                                    tool_calls_acc[idx]["function"][
                                        "arguments"
                                    ] += tc_delta.function.arguments
                if chunk.usage:
                    usage = chunk.usage.model_dump()

            message_dict = {
                "role": "assistant",
                "content": "".join(content_parts) or None,
                "tool_calls": list(tool_calls_acc.values()) if tool_calls_acc else None,
            }
            yield message_dict, usage
            return
        except Exception as e:
            print(f"Model exception: {e}")
    raise Exception("Failed to invoke model after 3 attempts.")


async def _inline_content_images(parts: list[dict]) -> list[dict]:
    """Replace remote image URLs with cached base64 data URLs."""
    inlined: list[dict] = []
    for part in parts:
        if part.get("type") == "image_url":
            url = part.get("image_url", {}).get("url", "")
            if url and not url.startswith("data:"):
                try:
                    part = {"type": "image_url", "image_url": {"url": await inline_image_url(url)}}
                except Exception as e:
                    print(f"Failed to inline image {url}: {e}")
        inlined.append(part)
    return inlined


async def _convert_history(contents: list[dict]) -> list[dict]:
    messages: list[dict] = []
    for msg in contents:
        role = msg.get("role")
        if role in ("user", "model"):
            content = msg.get("content")
            if isinstance(content, list):
                content = await _inline_content_images(content)
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
    _sanitize_tool_calls(messages)
    return messages


def _get_tool_response(tool_call: dict, user_id: str) -> dict:
    try:
        args = json.loads(tool_call["function"]["arguments"])
    except json.JSONDecodeError:
        args = {}
    name = tool_call["function"]["name"]
    response = None
    try:
        match name:
            case "search":
                response = tools.search_tool(user_id=user_id, **args)
            case "web_search":
                response = tools.web_search_tool(**args)
            case "web_fetch":
                response = {"results": tools.web_fetch_tool(**args)}
            # Ingredients
            case "get_ingredient_by_id":
                response = {
                    "ingredient": tools.get_ingredient_by_id_tool(
                        user_id=user_id, ingredient_id=args["ingredient_id"]
                    )
                }
            case "insert_ingredient":
                response = {"ingredient": tools.insert_ingredient_tool(user_id=user_id, **args)}
            case "update_ingredient":
                tools.update_ingredient_tool(user_id=user_id, **args)
                response = {"success": True}
            case "delete_ingredient":
                tools.delete_ingredient_tool(user_id=user_id, ingredient_id=args["ingredient_id"])
                response = {"success": True}
            # Serving Sizes
            case "get_serving_sizes_by_ingredient_id":
                response = {
                    "serving_sizes": tools.get_serving_sizes_by_ingredient_id_tool(
                        user_id=user_id, ingredient_id=args["ingredient_id"]
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
            # Recipes
            case "get_recipe_by_id":
                response = {
                    "recipe": tools.get_recipe_by_id_tool(
                        user_id=user_id, recipe_id=args["recipe_id"]
                    )
                }
            case "insert_recipe":
                response = {"recipe": tools.insert_recipe_tool(user_id=user_id, **args)}
            case "update_recipe":
                tools.update_recipe_tool(user_id=user_id, **args)
                response = {"success": True}
            case "delete_recipe":
                tools.delete_recipe_tool(user_id=user_id, recipe_id=args["recipe_id"])
                response = {"success": True}
            # Logs
            case "get_daily_summary":
                response = tools.get_daily_summary_tool(
                    user_id=user_id, day=args["day"]
                )
            case "insert_log_by_grams":
                tools.insert_log_by_grams_tool(user_id=user_id, **args)
                response = {"success": True}
            case "insert_log_by_serving_size":
                tools.insert_log_by_serving_size_tool(user_id=user_id, **args)
                response = {"success": True}
            case "update_log":
                tools.update_log_tool(user_id=user_id, **args)
                response = {"success": True}
            case "delete_log":
                tools.delete_log_tool(
                    user_id=user_id, log_id=args["log_id"]
                )
                response = {"success": True}
            # Goals
            case "get_current_goal":
                response = {"goal": tools.get_current_goal_tool(user_id=user_id)}
            case "insert_goal":
                tools.insert_goal_tool(user_id=user_id, **args)
                response = {"success": True}
            # Measurements
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
) -> AsyncGenerator[dict | models.ContentTokenStep | models.ToolCallStartStep, None]:
    messages: list[dict] = [
        {"role": "system", "content": input.system_prompt},
        *await _convert_history(input.contents),
    ]
    model_id = input.model or providers.DEFAULT_MODEL_ID
    provider = providers.get_provider(model_id)
    for _ in range(MAX_TURNS):
        _sanitize_tool_calls(messages)
        async for chunk in _invoke_model(model_id, messages):
            if isinstance(chunk, tuple):
                message_dict, usage = chunk
                if usage:
                    uncached_input, cached_input, output = extract_tokens(usage)
                    if provider == "mimo":
                        cost = get_mimo_cost(model_id=model_id, usage=usage)
                    else:
                        cost = await get_openrouter_cost(model_id=model_id, usage=usage)
                    print(f"Invocation cost: ${cost}")
                    repository.insert_llm_invocation(
                        total_cost=cost,
                        raw_usage_metadata=usage,
                        model_id=model_id,
                        uncached_input_tokens=uncached_input,
                        cached_input_tokens=cached_input,
                        output_tokens=output,
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
            else:
                yield chunk
    raise Exception("Maximum number of turns reached without reaching a conclusion.")
