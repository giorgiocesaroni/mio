import base64
import datetime
from typing import AsyncGenerator
from uuid import UUID
import src.agent.models as models
import src.agent.repository as repository
from src.agent.agent import agent
import src.agent.prompts as prompts


def _convert_input(message: models.MessageType) -> models.Content:
    parts = []
    for part in message.parts:
        if part.text:
            parts.append(models.Part(text=part.text))
        elif part.data:
            parts.append(
                models.Part.from_bytes(
                    data=part.data,
                    mime_type=part.mime_type or "application/octet-stream",
                )
            )
    return models.Content(role="user", parts=parts)


async def run_agent(
    input: models.RunAgentInput,
) -> AsyncGenerator[models.RunAgentStep, None]:
    user_input = _convert_input(input.message)
    repository.create_conversation_if_not_exists(input.conversation_id, input.user_id)
    repository.insert_conversation_message(input.conversation_id, user_input, input.user_id)
    contents = repository.get_messages_by_conversation_id(input.conversation_id, input.user_id)
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    daily_macros = repository.get_daily_macros(today, input.user_id)
    current_goal = repository.get_current_goal(input.user_id)
    system_prompt = prompts.get_system_prompt(
        daily_macros=daily_macros,
        current_goal=current_goal.model_dump() if current_goal else None,
    )
    if input.channel_instructions:
        system_prompt = f"{system_prompt}\n\n{input.channel_instructions}"

    agent_input = models.AgentInput(
        conversation_id=input.conversation_id,
        user_id=input.user_id,
        system_prompt=system_prompt,
        contents=[*contents, user_input],
    )
    async for content in agent(agent_input):
        repository.insert_conversation_message(input.conversation_id, content, input.user_id)
        if content.role == "model" and content.parts:
            for part in content.parts:
                if part.function_call and part.function_call.name:
                    yield models.ToolCallStep(
                        type="tool_call",
                        name=part.function_call.name,
                        args=part.function_call.args or {},
                    )
                if part.text:
                    yield models.MessageStep(
                        type="message",
                        text=part.text,
                    )


def get_total_usage() -> dict:
    return repository.get_total_llm_usage()


def get_conversation_usage(conversation_id: UUID) -> dict:
    return repository.get_conversation_llm_usage(conversation_id)


def get_conversation_history(conversation_id: UUID, user_id: str) -> list[models.RunAgentStep]:
    contents = repository.get_messages_by_conversation_id(conversation_id, user_id)
    steps: list[models.RunAgentStep] = []
    for content in contents:
        if content.role == "user" and content.parts:
            for part in content.parts:
                if part.text:
                    steps.append(
                        models.UserMessageStep(type="user_message", text=part.text)
                    )
                elif part.inline_data:
                    data_b64 = base64.b64encode(part.inline_data.data).decode()
                    mime = part.inline_data.mime_type
                    label = (
                        "Image"
                        if mime.startswith("image/")
                        else "Audio" if mime.startswith("audio/") else "File"
                    )
                    steps.append(
                        models.UserMessageStep(
                            type="user_message",
                            text=label,
                            data=data_b64,
                            mime_type=mime,
                        )
                    )
        elif content.role == "model" and content.parts:
            for part in content.parts:
                if part.text:
                    steps.append(models.MessageStep(type="message", text=part.text))
                if part.function_call and part.function_call.name:
                    steps.append(
                        models.ToolCallStep(
                            type="tool_call",
                            name=part.function_call.name,
                            args=part.function_call.args or {},
                        )
                    )
    return steps
