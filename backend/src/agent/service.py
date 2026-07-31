import base64
import datetime
import json
from typing import AsyncGenerator
from uuid import UUID
from zoneinfo import ZoneInfo
import src.agent.models as models
import src.agent.repository as repository
from src.agent.agent import agent
import src.agent.prompts as prompts
from src.api.transcribe import transcribe_audio


async def _fetch_audio_from_url(url: str) -> tuple[bytes, str]:
    """Fetch audio data from a URL. Returns (audio_bytes, mime_type)."""
    import httpx
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        mime_type = response.headers.get("content-type", "audio/ogg")
        return response.content, mime_type


async def _preprocess_message(
    message: models.MessageType,
    user_id: str,
    conversation_id: UUID,
) -> models.MessageType:
    """Preprocess message by transcribing audio parts to text."""
    new_parts = []
    for part in message.parts:
        if part.url and part.mime_type and part.mime_type.startswith("audio/"):
            audio_data, _ = await _fetch_audio_from_url(part.url)
            result = await transcribe_audio(audio_data, part.mime_type)
            repository.insert_llm_invocation(
                total_cost=result.cost,
                raw_usage_metadata=result.usage,
                user_id=user_id,
                conversation_id=conversation_id,
            )
            new_parts.append(models.UserMessagePart(text=result.text))
        elif part.data and part.mime_type and part.mime_type.startswith("audio/"):
            result = await transcribe_audio(part.data, part.mime_type)
            repository.insert_llm_invocation(
                total_cost=result.cost,
                raw_usage_metadata=result.usage,
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


async def run_agent(
    input: models.RunAgentInput,
) -> AsyncGenerator[models.RunAgentStep, None]:
    repository.create_conversation_if_not_exists(input.conversation_id, input.user_id)
    preprocessed_message = await _preprocess_message(
        input.message, input.user_id, input.conversation_id
    )
    user_input = _convert_input(preprocessed_message)
    repository.insert_conversation_message(
        input.conversation_id, user_input, input.user_id
    )
    contents = repository.get_messages_by_conversation_id(
        input.conversation_id, input.user_id
    )
    timezone = repository.get_user_timezone(input.user_id)
    today = datetime.datetime.now(tz=ZoneInfo(timezone)).strftime("%Y-%m-%d")
    daily_macros = repository.get_daily_macros(today, input.user_id)
    current_goal = repository.get_current_goal(input.user_id)
    system_prompt = prompts.get_system_prompt(
        daily_macros=daily_macros,
        current_goal=current_goal.model_dump(mode="json") if current_goal else None,
        timezone=timezone,
    )
    if input.channel_instructions:
        system_prompt = f"{system_prompt}\n\n{input.channel_instructions}"

    agent_input = models.AgentInput(
        conversation_id=input.conversation_id,
        user_id=input.user_id,
        system_prompt=system_prompt,
        contents=contents,
        thinking=input.thinking,
        model=input.model,
    )
    async for chunk in agent(agent_input):
        if isinstance(chunk, models.ContentTokenStep):
            yield chunk
        elif isinstance(chunk, models.ToolCallStartStep):
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


def get_total_usage() -> dict:
    return repository.get_total_llm_usage()


def get_conversation_usage(conversation_id: UUID) -> dict:
    return repository.get_conversation_llm_usage(conversation_id)


def get_conversation_history(
    conversation_id: UUID, user_id: str
) -> list[models.RunAgentStep]:
    messages = repository.get_messages_by_conversation_id(conversation_id, user_id)
    steps: list[models.RunAgentStep] = []
    for msg in messages:
        role = msg.get("role")
        if role == "user":
            content = msg.get("content")
            if isinstance(content, str):
                steps.append(models.UserMessageStep(type="user_message", text=content))
            elif isinstance(content, list):
                for part in content:
                    if part.get("type") == "text":
                        steps.append(
                            models.UserMessageStep(
                                type="user_message", text=part["text"]
                            )
                        )
                    elif part.get("type") == "image_url":
                        url = part.get("image_url", {}).get("url", "")
                        label = "Image"
                        if url.startswith("data:"):
                            header, _ = url.split(",", 1)
                            mime = header.split(":")[1].split(";")[0]
                            label = (
                                "Image"
                                if mime.startswith("image/")
                                else "Audio"
                                if mime.startswith("audio/")
                                else "File"
                            )
                        steps.append(
                            models.UserMessageStep(
                                type="user_message",
                                text=label,
                                data=url,
                                mime_type="url" if not url.startswith("data:") else None,
                            )
                        )
                    elif part.get("type") == "input_audio":
                        url = part.get("input_audio", {}).get("data", "")
                        label = "Audio"
                        if url.startswith("data:"):
                            header, _ = url.split(",", 1)
                            mime = header.split(":")[1].split(";")[0]
                        else:
                            mime = "audio/ogg"
                        steps.append(
                            models.UserMessageStep(
                                type="user_message",
                                text=label,
                                data=url,
                                mime_type="url" if not url.startswith("data:") else mime,
                            )
                        )
        elif role == "assistant":
            content = msg.get("content")
            if content:
                steps.append(models.MessageStep(type="message", text=content))
            for tc in msg.get("tool_calls") or []:
                func = tc["function"]
                try:
                    args = json.loads(func["arguments"])
                except json.JSONDecodeError:
                    args = {}
                steps.append(
                    models.ToolCallStep(
                        type="tool_call",
                        name=func["name"],
                        args=args,
                    )
                )
    return steps
