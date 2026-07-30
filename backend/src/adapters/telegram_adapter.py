from dotenv import load_dotenv

load_dotenv()

import logging
import os
import uuid
from typing import Dict
from uuid import UUID

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
)
from telegram.ext.filters import COMMAND
import src.agent.models as models
import src.agent.service as service
from src.agent.utils import summarize_large_numbers

logger = logging.getLogger(__name__)

telegram_app = ApplicationBuilder().token(os.getenv("TELEGRAM_BOT_TOKEN", "")).build()

_chat_conversations: Dict[int, UUID] = {}


def _get_or_create_conversation_id(chat_id: int) -> UUID:
    if chat_id not in _chat_conversations:
        _chat_conversations[chat_id] = uuid.uuid4()
    return _chat_conversations[chat_id]


async def _answer_message(update: Update, _: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    chat_id = update.message.chat_id
    conversation_id = _get_or_create_conversation_id(chat_id)

    user_text = update.message.text
    user_voice = update.message.voice
    user_photo = update.message.photo

    parts: list[models.UserMessagePart] = []

    if user_text:
        parts.append(models.UserMessagePart(text=user_text))
    if user_voice:
        voice = await user_voice.get_file()
        parts.append(
            models.UserMessagePart(
                data=await voice.download_as_bytearray(),
                mime_type="audio/ogg",
            )
        )
    if user_photo:
        photo = await user_photo[-1].get_file()
        parts.append(
            models.UserMessagePart(
                data=await photo.download_as_bytearray(),
                mime_type="image/jpeg",
            )
        )
    if update.message.caption:
        parts.append(models.UserMessagePart(text=update.message.caption))

    if not parts:
        return

    message = models.RunAgentUserMessage(parts=parts)

    inp = models.RunAgentInput(
        conversation_id=conversation_id,
        message=message,
        channel_instructions=(
            "You are chatting through Telegram, a popular messaging app. "
            "Telegram's text parsing is a bit basic; "
            "use emojis exclusively for formatting and emphasis, "
            "and avoid using Markdown or HTML tags in your responses."
        ),
    )

    try:
        await update.message.chat.send_action("typing")
        async for step in service.run_agent(inp):
            if isinstance(step, models.MessageStep):
                try:
                    await update.message.reply_html(step.text)
                except Exception:
                    await update.message.reply_text(step.text)
            elif isinstance(step, models.ToolCallStep):
                text = f"⚙️ Tool call: <code>{step.name}</code>"
                try:
                    await update.message.reply_html(text)
                except Exception:
                    pass
    except Exception as e:
        logger.error(f"Error running agent: {e}")
        await update.message.reply_html(f"🫣 {e}")


async def _new_conversation(update: Update, _: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    chat_id = update.message.chat_id
    conversation_id = uuid.uuid4()
    _chat_conversations[chat_id] = conversation_id
    await update.message.reply_html(
        f"⚙️ Started new conversation with ID: <code>{conversation_id}</code>."
    )


async def _show_usage(update: Update, _: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    total = service.get_total_usage()
    text = (
        "⚙️ <b>Usage Report</b>\n\n"
        "<b>All conversations</b>\n"
        f"⬆️ <code>{summarize_large_numbers(total['prompt_tokens'])}</code> input tokens\n"
        f"⬇️ <code>{summarize_large_numbers(total['completion_tokens'])}</code> output tokens\n"
        f"💰 <code>${total['total_cost']:.4f}</code> total cost"
    )

    chat_id = update.message.chat_id
    conversation_id = _chat_conversations.get(chat_id)
    if conversation_id:
        conv = service.get_conversation_usage(conversation_id)
        text += (
            "\n\n<b>This conversation</b>\n"
            f"⬆️ <code>{summarize_large_numbers(conv['prompt_tokens'])}</code> input tokens\n"
            f"⬇️ <code>{summarize_large_numbers(conv['completion_tokens'])}</code> output tokens\n"
            f"💰 <code>${conv['total_cost']:.4f}</code> cost"
        )

    await update.message.reply_html(text)


telegram_app.add_handlers(
    [
        CommandHandler("new", _new_conversation),
        CommandHandler("usage", _show_usage),
        MessageHandler(~COMMAND, _answer_message),
    ]
)

if __name__ == "__main__":
    print("Starting Telegram bot...")
    telegram_app.run_polling()
