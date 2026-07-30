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


def _convert_input(message: models.MessageType) -> dict:
    parts = []
    for part in message.parts:
        if part.text:
            parts.append({"type": "text", "text": part.text})
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
    user_input = _convert_input(input.message)
    repository.create_conversation_if_not_exists(input.conversation_id, input.user_id)
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
    )
    async for message in agent(agent_input):
        repository.insert_conversation_message(
            input.conversation_id, message, input.user_id
        )
        role = message.get("role")
        if role == "assistant":
            content = message.get("content")
            if content:
                yield models.MessageStep(type="message", text=content)
            for tc in message.get("tool_calls") or []:
                func = tc["function"]
                yield models.ToolCallStep(
                    type="tool_call",
                    name=func["name"],
                    args=json.loads(func["arguments"]),
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
                        if url.startswith("data:"):
                            header, b64data = url.split(",", 1)
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
                                    data=b64data,
                                    mime_type=mime,
                                )
                            )
        elif role == "assistant":
            content = msg.get("content")
            if content:
                steps.append(models.MessageStep(type="message", text=content))
            for tc in msg.get("tool_calls", []):
                func = tc["function"]
                steps.append(
                    models.ToolCallStep(
                        type="tool_call",
                        name=func["name"],
                        args=json.loads(func["arguments"]),
                    )
                )
    return steps
