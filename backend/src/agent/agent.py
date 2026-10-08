import json
import os
import re
import anthropic
import src.agent.models as models
import src.agent.providers as providers
import src.agent.repository as repository
import src.agent.tools as tools
import src.pipeline.logic as pipeline_logic
import src.pipeline.service as pipeline
from src.agent.utils import extract_tokens, image_block, inline_image_url
from typing import AsyncGenerator
from uuid import UUID

MAX_TURNS = 35

# Maximum output tokens per model invocation. Thinking counts toward it, so
# it's generous; only the tokens used are paid for. Too low shows up as the
# model stopping mid-sentence or a truncated tool call.
MAX_COMPLETION_TOKENS = int(os.getenv("MAX_COMPLETION_TOKENS", "16384"))

# What the user sees when the model declines or runs out of tokens with nothing said.
REFUSAL_REPLY = "Sorry, I can't help with that one."
TRUNCATED_REPLY = "Sorry, my answer got cut off. Could you ask again?"


# What the agent is doing while a tool runs, shown to the user.
TOOL_STATUS = {
    "search": "Searching your foods",
    "web_search": "Searching the web",
    "web_fetch": "Reading sources",
    "get_ingredient_by_id": "Looking up your foods",
    "insert_ingredient": "Saving the ingredient",
    "update_ingredient": "Updating the ingredient",
    "delete_ingredient": "Deleting the ingredient",
    "get_serving_sizes_by_ingredient_id": "Looking up serving sizes",
    "insert_serving_size": "Saving the serving size",
    "update_serving_size": "Updating the serving size",
    "delete_serving_size": "Deleting the serving size",
    "get_recipe_by_id": "Looking up the recipe",
    "insert_recipe": "Saving the recipe",
    "update_recipe": "Updating the recipe",
    "delete_recipe": "Deleting the recipe",
    "get_daily_summary": "Checking your day",
    "log_food": "Logging foods",
    "update_logs": "Updating your logs",
    "delete_logs": "Deleting logs",
    "get_current_goal": "Checking your goal",
    "insert_goal": "Saving your goal",
    "get_latest_measurements": "Checking your measurements",
    "insert_measurement": "Saving your measurement",
}


def _tool_status(name: str) -> models.StatusStep:
    return models.StatusStep(text=TOOL_STATUS.get(name, "Working"))


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
    tools.log_food_declaration,
    tools.update_logs_declaration,
    tools.delete_logs_declaration,
    tools.get_current_goal_declaration,
    tools.insert_goal_declaration,
    tools.get_latest_measurements_declaration,
    tools.insert_measurement_declaration,
]


def _to_tools(declarations: list) -> list[dict]:
    return [
        {
            "name": d.name,
            "description": d.description,
            "input_schema": d.parameters_json_schema,
        }
        for d in declarations
    ]


def _with_cache_breakpoint(messages: list[dict]) -> list[dict]:
    """`messages` with a cache breakpoint on the last user message, so the
    tools, the system prompt and the conversation up to it are cached for the
    next tool round and the next turn. Not on the trailing system message: a
    breakpoint there didn't carry over to the next turn."""
    index = max(i for i, m in enumerate(messages) if m["role"] == "user")
    blocks = list(messages[index]["content"])
    blocks[-1] = {**blocks[-1], "cache_control": {"type": "ephemeral"}}
    return [
        *messages[:index],
        {**messages[index], "content": blocks},
        *messages[index + 1 :],
    ]


async def _invoke_model(
    system: str,
    messages: list[dict],
) -> AsyncGenerator[
    anthropic.types.Message | models.ContentTokenStep | models.ToolCallStartStep, None
]:
    """Stream a model response, yielding content tokens, tool call starts, and
    the final message."""
    client = providers.get_client()
    messages = _with_cache_breakpoint(messages)
    for _ in range(3):
        try:
            async with client.messages.stream(
                model=providers.MODEL,
                max_tokens=MAX_COMPLETION_TOKENS,
                system=system,
                messages=messages,
                tools=_to_tools(TOOL_DECLARATIONS),
                output_config={"effort": providers.EFFORT},
            ) as stream:
                async for event in stream:
                    if event.type == "text":
                        yield models.ContentTokenStep(token=event.text)
                    elif (
                        event.type == "content_block_start"
                        and event.content_block.type == "tool_use"
                    ):
                        yield models.ToolCallStartStep(name=event.content_block.name)
                response = await stream.get_final_message()
            print(
                f"[INFO] {providers.MODEL}: finished "
                f"(stop_reason={response.stop_reason}, "
                f"output_tokens={response.usage.output_tokens})."
            )
            yield response
            return
        except anthropic.BadRequestError:
            # The same request fails the same way again.
            raise
        except Exception as e:
            print(f"Model exception: {e}")
    raise Exception("Failed to invoke model after 3 attempts.")


def _app_message(response: anthropic.types.Message) -> dict:
    """The assistant message as the app stores and streams it: its text, its
    tool calls with JSON arguments, and `blocks`, the response exactly as it
    came (thinking included), which is what the model is sent back."""
    text = "".join(b.text for b in response.content if b.type == "text")
    calls = [b for b in response.content if b.type == "tool_use"]
    blocks = [b.model_dump(exclude_none=True) for b in response.content]
    if response.stop_reason in ("refusal", "max_tokens"):
        # A refusal can cut a tool call off, and so can the token limit.
        print(f"[WARN] {providers.MODEL}: stopped early ({response.stop_reason}).")
        # Not sent back: what's stored is the reply the user saw.
        calls, blocks = [], []
        if not text.strip():
            text = REFUSAL_REPLY if response.stop_reason == "refusal" else TRUNCATED_REPLY
    return {
        "role": "assistant",
        "content": text or None,
        "tool_calls": [
            {
                "id": c.id,
                "type": "function",
                "function": {"name": c.name, "arguments": json.dumps(c.input)},
            }
            for c in calls
        ]
        or None,
        **({"blocks": blocks} if blocks else {}),
    }


async def _inline_content_images(parts: list[dict]) -> list[dict]:
    """Replace remote image URLs with cached base64 data URLs. A photo that
    can't be fetched fails the turn: sending anything else in its place would
    rewrite an earlier turn."""
    inlined: list[dict] = []
    for part in parts:
        if part.get("type") == "image_url":
            url = part.get("image_url", {}).get("url", "")
            if url and not url.startswith("data:"):
                try:
                    part = {
                        "type": "image_url",
                        "image_url": {"url": await inline_image_url(url)},
                    }
                except Exception as e:
                    raise RuntimeError(f"Couldn't load a photo in this chat: {e}") from e
        inlined.append(part)
    return inlined


def _tool_use_id(call_id: str) -> str:
    """Tool call ids from earlier providers, made valid for Anthropic."""
    return re.sub(r"[^a-zA-Z0-9_-]", "_", call_id or "") or "call"


def _user_blocks(content: str | list) -> list[dict]:
    """A stored user message's content as Anthropic content blocks."""
    if isinstance(content, str):
        return [{"type": "text", "text": content}] if content.strip() else []
    blocks: list[dict] = []
    for part in content:
        if part.get("type") == "text" and (part.get("text") or "").strip():
            blocks.append({"type": "text", "text": part["text"]})
        elif part.get("type") == "image_url":
            url = part.get("image_url", {}).get("url", "")
            if url.startswith("data:"):
                blocks.append(image_block(url))
    return blocks


def _arguments(raw: str) -> dict:
    try:
        args = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return args if isinstance(args, dict) else {}


def _to_anthropic(messages: list[dict]) -> list[dict]:
    """Stored messages (user text and photos, assistant text and tool calls,
    tool results) as Anthropic messages: tool calls become `tool_use` blocks,
    and their results `tool_result` blocks in the next user message. A user
    message's context (when it was sent) follows it as a system message. Calls
    left without a result (an interrupted turn) get an error result, and
    consecutive messages of one role are merged."""
    converted: list[dict] = []
    pending: list[str] = []  # tool_use ids still waiting for a result

    def add(role: str, blocks: list[dict]) -> None:
        if not blocks:
            return
        # A system message must be followed by the assistant's reply. One
        # that wasn't (its turn failed) is dropped: nothing came after it.
        if converted and converted[-1]["role"] == "system" and role != "assistant":
            converted.pop()
        if converted and converted[-1]["role"] == role:
            converted[-1]["content"].extend(blocks)
        else:
            converted.append({"role": role, "content": blocks})

    def close_pending() -> None:
        add(
            "user",
            [
                {
                    "type": "tool_result",
                    "tool_use_id": call_id,
                    "content": json.dumps({"error": "Interrupted."}),
                    "is_error": True,
                }
                for call_id in pending
            ],
        )
        pending.clear()

    for msg in messages:
        role = msg.get("role")
        if role == "tool":
            call_id = _tool_use_id(msg.get("tool_call_id", ""))
            if call_id in pending:
                pending.remove(call_id)
                add(
                    "user",
                    [
                        {
                            "type": "tool_result",
                            "tool_use_id": call_id,
                            "content": msg.get("content") or "{}",
                        }
                    ],
                )
            continue
        close_pending()
        if role == "user":
            add("user", _user_blocks(msg.get("content") or ""))
            if msg.get("context") and converted and converted[-1]["role"] == "user":
                converted.append({"role": "system", "content": msg["context"]})
        elif role == "assistant" and msg.get("blocks"):
            # The model's response exactly as it came, thinking included.
            add("assistant", list(msg["blocks"]))
            pending.extend(
                b["id"] for b in msg["blocks"] if b.get("type") == "tool_use"
            )
        elif role == "assistant":
            blocks: list[dict] = []
            if isinstance(msg.get("content"), str) and msg["content"].strip():
                blocks.append({"type": "text", "text": msg["content"]})
            for tc in msg.get("tool_calls") or []:
                call_id = _tool_use_id(tc.get("id", ""))
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": call_id,
                        "name": tc["function"]["name"],
                        "input": _arguments(tc["function"].get("arguments", "")),
                    }
                )
                pending.append(call_id)
            add("assistant", blocks)
    close_pending()
    return converted


async def _convert_history(contents: list[dict]) -> list[dict]:
    """Stored messages as the app's own format, every photo inlined. Earlier
    turns go to the model exactly as they did the first time: a change would
    lose the prompt cache and invalidate the thinking that came after it."""
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
                        **({"context": msg["context"]} if msg.get("context") else {}),
                    }
                )
            elif "parts" in msg:
                text_parts = []
                for part in msg["parts"]:
                    if isinstance(part, dict) and part.get("text"):
                        text_parts.append(part["text"])
                if text_parts:
                    messages.append(
                        {
                            "role": "user" if role == "user" else "assistant",
                            "content": "\n".join(text_parts),
                        }
                    )
            continue
        if role in ("assistant", "tool"):
            messages.append(msg)
    return messages


def _as_queries(args: dict) -> dict:
    """Accept a single `query` (older history or a misparse) as a one-item batch."""
    if "queries" not in args and isinstance(args.get("query"), str):
        args = {**args, "queries": [args["query"]]}
        args.pop("query")
    return args


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
                response = tools.search_tool(user_id=user_id, **_as_queries(args))
            case "web_search":
                response = tools.web_search_tool(**_as_queries(args))
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
                response = {
                    "ingredient": tools.insert_ingredient_tool(user_id=user_id, **args)
                }
            case "update_ingredient":
                tools.update_ingredient_tool(user_id=user_id, **args)
                response = {"success": True}
            case "delete_ingredient":
                tools.delete_ingredient_tool(
                    user_id=user_id, ingredient_id=args["ingredient_id"]
                )
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
            case "update_logs":
                response = tools.update_logs_tool(user_id=user_id, **args)
            case "delete_logs":
                response = tools.delete_logs_tool(user_id=user_id, **args)
            # Logging always goes through a draft (`log_food`), including for
            # older tool names still present in stored conversation history.
            case "log_entries" | "log_ingredient" | "log_recipe":
                response = {"error": "Log foods with `log_food`."}
            # Legacy singular names, still present in stored conversation
            # history, mapped onto the batched tools.
            case "update_log":
                response = tools.update_logs_tool(user_id=user_id, updates=[args])
            case "delete_log":
                response = tools.delete_logs_tool(
                    user_id=user_id, log_ids=[args["log_id"]]
                )
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


def log_food_result(draft: dict) -> dict:
    """What the agent sees of a draft `log_food` created."""
    return {
        "draft_id": draft["id"],
        "day": draft["day"],
        "status": "awaiting_user_confirmation",
        "entries": [
            {
                "food": pipeline_logic.row_label(row),
                "meal_type": row["meal_type"],
                "log_for": row["log_for"],
                "note": row["note"],
            }
            for row in draft["rows"]
        ],
    }


def _latest_image_urls(contents: list[dict]) -> list[str]:
    """Image URLs of the user's latest message, which `log_food` drafts from too."""
    for msg in reversed(contents):
        if msg.get("role") != "user":
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            return []
        return [
            part["image_url"]["url"]
            for part in content
            if part.get("type") == "image_url" and part.get("image_url", {}).get("url")
        ]
    return []


async def _log_food(
    tool_call: dict, input: models.AgentInput
) -> AsyncGenerator[models.StatusStep | tuple[dict, dict | None], None]:
    """Run `log_food` through the logging pipeline, streaming its statuses;
    the last item is (tool result, draft)."""
    try:
        args = json.loads(tool_call["function"]["arguments"])
    except json.JSONDecodeError:
        args = {}
    draft = None
    replaces = args.get("replaces_draft_id")
    try:
        # Checked first, so a correction to a draft the user already
        # confirmed doesn't draft the same foods twice.
        if replaces:
            old = pipeline.get_draft(input.user_id, UUID(replaces))
            if not old or old["status"] != "pending":
                raise ValueError(
                    "That draft was already confirmed or discarded, so it can't be "
                    "replaced; correct logged foods with `update_logs` or `delete_logs`."
                )
        async for step in pipeline.draft_food(
            input.user_id,
            args.get("description", ""),
            _latest_image_urls(input.contents),
            args.get("day"),
        ):
            if step.type == "stage":
                # Its message was read already: the statuses start at extraction.
                if step.name != "normalize" and (
                    status := pipeline_logic.status_after(step)
                ):
                    yield models.StatusStep(text=status)
            elif step.outcome == "drafted" and step.draft:
                draft = step.draft
            else:
                raise ValueError(step.message)
        if replaces:
            pipeline.discard_draft(input.user_id, UUID(replaces))
        response = log_food_result(draft)
    except Exception as e:
        response = {"error": str(e)}
    yield {
        "tool_call_id": tool_call["id"],
        "role": "tool",
        "content": json.dumps(response),
    }, draft


async def agent(
    input: models.AgentInput,
) -> AsyncGenerator[
    dict
    | models.ContentTokenStep
    | models.ToolCallStartStep
    | models.DraftStep
    | models.StatusStep,
    None,
]:
    # The model's view of the conversation: earlier turns exactly as they were
    # sent, and its responses as they came, thinking included.
    messages = _to_anthropic(await _convert_history(input.contents))
    # What this turn cost, counted toward the drafts it creates.
    turn_cost = 0.0
    draft_ids: list[str] = []
    for _ in range(MAX_TURNS):
        yield models.StatusStep(text="Thinking")
        async for chunk in _invoke_model(input.system_prompt, messages):
            if isinstance(chunk, anthropic.types.Message):
                response = chunk
                usage = response.usage.model_dump(exclude_none=True)
                uncached_input, cached_input, output = extract_tokens(usage)
                cost = providers.cost(usage)
                print(f"Invocation cost: ${cost}")
                turn_cost += cost
                repository.insert_llm_invocation(
                    total_cost=cost,
                    raw_usage_metadata=usage,
                    model_id=providers.MODEL,
                    uncached_input_tokens=uncached_input,
                    cached_input_tokens=cached_input,
                    output_tokens=output,
                    user_id=input.user_id,
                    conversation_id=input.conversation_id,
                )
                message_dict = _app_message(response)
                yield message_dict
                tool_calls = message_dict.get("tool_calls") or []
                if not tool_calls:
                    for draft_id in draft_ids:
                        pipeline.add_draft_cost(draft_id, turn_cost / len(draft_ids))
                    return
                # The same blocks the stored message replays on later turns.
                messages.append({"role": "assistant", "content": message_dict["blocks"]})
                results: list[dict] = []
                for tc in tool_calls:
                    yield _tool_status(tc["function"]["name"])
                    if tc["function"]["name"] == "log_food":
                        async for item in _log_food(tc, input):
                            if isinstance(item, models.StatusStep):
                                yield item
                            else:
                                tool_result, draft = item
                        if draft:
                            draft_ids.append(draft["id"])
                            yield models.DraftStep(draft=draft)
                    else:
                        tool_result = _get_tool_response(tc, input.user_id)
                    results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tc["id"],
                            "content": tool_result["content"],
                        }
                    )
                    yield tool_result
                # Every result of a round in one message.
                messages.append({"role": "user", "content": results})
            else:
                yield chunk
                if isinstance(chunk, models.ToolCallStartStep):
                    yield _tool_status(chunk.name)
    raise Exception("Maximum number of turns reached without reaching a conclusion.")
