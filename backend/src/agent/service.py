import base64
import datetime
import json
import uuid
from typing import AsyncGenerator
from uuid import UUID
from zoneinfo import ZoneInfo
import src.agent.models as models
import src.agent.repository as repository
from src.agent.agent import agent, log_food_result
import src.agent.prompts as prompts
import src.pipeline.logic as pipeline_logic
import src.pipeline.service as pipeline
from src.pipeline.models import PipelineInput
from src.agent.utils import extract_tokens
from src.api.transcribe import transcribe_audio, MODEL_ID as TRANSCRIBE_MODEL_ID


async def _fetch_audio_from_url(url: str) -> tuple[bytes, str]:
    """Fetch audio data from a URL. Returns (audio_bytes, mime_type)."""
    import httpx
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        mime_type = response.headers.get("content-type", "audio/ogg")
        return response.content, mime_type


async def preprocess_message(
    message: models.MessageType,
    user_id: str,
    conversation_id: UUID | None,
) -> models.MessageType:
    """Preprocess message by transcribing audio parts to text."""
    new_parts = []
    for part in message.parts:
        if part.url and part.mime_type and part.mime_type.startswith("audio/"):
            audio_data, _ = await _fetch_audio_from_url(part.url)
            result = await transcribe_audio(audio_data, part.mime_type)
            uncached_input, cached_input, output = extract_tokens(result.usage)
            repository.insert_llm_invocation(
                total_cost=result.cost,
                raw_usage_metadata=result.usage,
                model_id=TRANSCRIBE_MODEL_ID,
                uncached_input_tokens=uncached_input,
                cached_input_tokens=cached_input,
                output_tokens=output,
                user_id=user_id,
                conversation_id=conversation_id,
            )
            new_parts.append(models.UserMessagePart(text=result.text))
        elif part.data and part.mime_type and part.mime_type.startswith("audio/"):
            result = await transcribe_audio(part.data, part.mime_type)
            uncached_input, cached_input, output = extract_tokens(result.usage)
            repository.insert_llm_invocation(
                total_cost=result.cost,
                raw_usage_metadata=result.usage,
                model_id=TRANSCRIBE_MODEL_ID,
                uncached_input_tokens=uncached_input,
                cached_input_tokens=cached_input,
                output_tokens=output,
                user_id=user_id,
                conversation_id=conversation_id,
            )
            new_parts.append(models.UserMessagePart(text=result.text))
        else:
            new_parts.append(part)
    return type(message)(parts=new_parts)


def _convert_input(message: models.MessageType) -> dict:
    parts = []
    for part in message.parts:
        if part.text:
            parts.append({"type": "text", "text": part.text})
        elif part.url:
            mime = part.mime_type or "application/octet-stream"
            if mime.startswith("audio/"):
                parts.append(
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": part.url,
                        },
                    }
                )
            else:
                parts.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": part.url,
                        },
                    }
                )
        elif part.data:
            mime = part.mime_type or "application/octet-stream"
            b64 = base64.b64encode(part.data).decode()
            if mime.startswith("audio/"):
                parts.append(
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": f"data:{mime};base64,{b64}",
                        },
                    }
                )
            else:
                parts.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime};base64,{b64}",
                        },
                    }
                )
    if len(parts) == 1 and parts[0].get("type") == "text":
        return {"role": "user", "content": parts[0]["text"]}
    return {"role": "user", "content": parts}


def _extract_title_from_parts(parts: list[models.UserMessagePart]) -> str | None:
    """Extract a title from message parts (first text part, truncated)."""
    for part in parts:
        if part.text:
            title = part.text.strip()
            return title[:100] if len(title) > 100 else title
    return None


async def run_agent(
    input: models.RunAgentInput,
) -> AsyncGenerator[models.RunAgentStep, None]:
    # Try to extract title from original message first
    title = _extract_title_from_parts(input.message.parts)

    # Create the conversation up front. Transcription (below) records an
    # llm_invocation referencing the conversation_id, and llm_invocations has a
    # foreign key to conversations — so the row must exist before we transcribe,
    # otherwise a brand-new conversation's first audio message would violate it.
    repository.create_conversation_if_not_exists(
        input.conversation_id, input.user_id, title
    )

    yield models.StatusStep(
        text="Transcribing"
        if any((p.mime_type or "").startswith("audio/") for p in input.message.parts)
        else "Reading your message"
    )
    # Preprocess message (transcribes audio)
    preprocessed_message = await preprocess_message(
        input.message, input.user_id, input.conversation_id
    )

    # If no title from original message (e.g. audio-only), derive it from the
    # now-transcribed text and backfill the conversation title.
    if title is None:
        transcribed_title = _extract_title_from_parts(preprocessed_message.parts)
        if transcribed_title is not None:
            repository.update_conversation_title(
                input.conversation_id, transcribed_title
            )
    user_input = _convert_input(preprocessed_message)
    repository.insert_conversation_message(
        input.conversation_id, user_input, input.user_id
    )
    contents = repository.get_messages_by_conversation_id(
        input.conversation_id, input.user_id
    )
    # Every message is routed: a new, self-contained food log is drafted by
    # the pipeline directly, which is faster and cheaper than the agent;
    # anything else, including whatever depends on the conversation, goes to
    # the agent, which sees the pipeline's drafts in the history.
    drafted = False
    async for step in _draft_directly(input, preprocessed_message, contents):
        drafted = drafted or isinstance(step, models.DraftStep)
        yield step
    if drafted:
        return
    timezone = repository.get_user_timezone(input.user_id)
    today = datetime.datetime.now(tz=ZoneInfo(timezone)).strftime("%Y-%m-%d")
    daily_macros = repository.get_daily_macros(today, input.user_id)
    current_goal = repository.get_current_goal(input.user_id)
    system_prompt = prompts.get_system_prompt(
        daily_macros=daily_macros,
        current_goal=current_goal.model_dump(mode="json") if current_goal else None,
        timezone=timezone,
        day=input.day,
    )

    agent_input = models.AgentInput(
        conversation_id=input.conversation_id,
        user_id=input.user_id,
        system_prompt=system_prompt,
        contents=contents,
        thinking=input.thinking,
        models=input.models,
    )
    async for chunk in agent(agent_input):
        if isinstance(
            chunk,
            (
                models.ContentTokenStep,
                models.ToolCallStartStep,
                models.DraftStep,
                models.StatusStep,
            ),
        ):
            yield chunk
        elif isinstance(chunk, dict):
            repository.insert_conversation_message(
                input.conversation_id, chunk, input.user_id
            )
            role = chunk.get("role")
            if role == "assistant":
                content = chunk.get("content")
                if content:
                    yield models.MessageStep(type="message", text=content)
                for tc in chunk.get("tool_calls") or []:
                    func = tc["function"]
                    try:
                        args = json.loads(func["arguments"])
                    except json.JSONDecodeError:
                        args = {}
                    yield models.ToolCallStep(
                        type="tool_call",
                        name=func["name"],
                        args=args,
                    )


def _routing_context(
    contents: list[dict], user_id: str
) -> tuple[str | None, list[str] | None]:
    """The assistant's latest reply, and the entries of the conversation's
    latest draft while it awaits confirmation: what the router weighs a new
    message against."""
    last_reply = next(
        (
            msg["content"]
            for msg in reversed(contents)
            if msg.get("role") == "assistant" and isinstance(msg.get("content"), str)
            and msg["content"]
        ),
        None,
    )
    latest = next(
        (
            draft
            for msg in reversed(contents)
            if msg.get("role") == "tool" and (draft := _drafted(msg, user_id))
        ),
        None,
    )
    pending = (
        [pipeline_logic.row_label(row) for row in latest["rows"]]
        if latest and latest["status"] == "pending"
        else None
    )
    return last_reply, pending


async def _draft_directly(
    input: models.RunAgentInput, message: models.MessageType, contents: list[dict]
) -> AsyncGenerator[models.RunAgentStep, None]:
    """Draft the message when the router finds it's a new food log.

    The draft is stored as a `log_food` call, so the agent sees it in the
    history and the conversation reloads the same way as when it drafts.
    Streams statuses, then the call and a `DraftStep`; without a `DraftStep`
    the message is the agent's.
    """
    last_reply, pending = _routing_context(contents, input.user_id)
    failed_stage = None
    async for step in pipeline.run(
        PipelineInput(
            user_id=input.user_id,
            message=message,
            day=input.day,
            last_reply=last_reply,
            pending_draft=pending,
            via="pipeline",
            models=input.models,
        )
    ):
        if step.type == "stage":
            if step.status == "error":
                failed_stage = step.name
            elif status := pipeline_logic.status_after(step):
                yield models.StatusStep(text=status)
            continue
        if step.outcome == "error":
            # Without a route, the agent can still handle the message.
            if failed_stage == "route":
                print(f"[WARN] Routing failed, falling back to the agent: {step.message}")
                return
            raise Exception(step.message)
        if step.outcome != "drafted" or not step.draft:
            return
        call_id = f"call_{uuid.uuid4().hex}"
        text = "\n".join(p.text for p in message.parts if p.text)
        args = {"description": text, "day": step.draft["day"]}
        repository.insert_conversation_message(
            input.conversation_id,
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": call_id,
                        "type": "function",
                        "function": {"name": "log_food", "arguments": json.dumps(args)},
                    }
                ],
            },
            input.user_id,
        )
        repository.insert_conversation_message(
            input.conversation_id,
            {
                "role": "tool",
                "tool_call_id": call_id,
                "content": json.dumps(log_food_result(step.draft)),
            },
            input.user_id,
        )
        yield models.ToolCallStep(type="tool_call", name="log_food", args=args)
        yield models.DraftStep(draft=step.draft)


def _drafted(tool_message: dict, user_id: str) -> dict | None:
    """The draft a `log_food` result created, as it is now."""
    try:
        result = json.loads(tool_message.get("content") or "")
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(result, dict) or not result.get("draft_id"):
        return None
    return pipeline.get_draft(user_id, UUID(result["draft_id"]))
