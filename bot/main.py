"""Telegram bot (aiogram) for the AI Customer Assistant.

The bot derives a stable `session_id` from the Telegram user id, forwards
messages to the FastAPI `/chat` endpoint, and returns the agent's reply.

Run:
    python -m bot.main
Requires TELEGRAM_BOT_TOKEN in the environment (.env).
"""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

from app.config import settings
from bot.client import AgentAPIClient

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("assistant.bot")

dp = Dispatcher()
api = AgentAPIClient()

WELCOME = (
    "👋 Hi! I'm your AI assistant. Ask about our services or pricing, or tell me "
    "about a project you need help with and I'll get you set up.\n\n"
    "Type /help for examples."
)

HELP = (
    "Try messages like:\n"
    "• What services do you offer?\n"
    "• How much does it cost?\n"
    "• I need help with a new project\n"
    "• Can I talk to a human?\n\n"
    "_Sample data shipped with this assistant is fictional and uses .example domains._"
)


def _session_id(message: Message) -> str:
    return f"tg-{message.from_user.id}" if message.from_user else "tg-unknown"


@dp.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(WELCOME, parse_mode="Markdown")


@dp.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP, parse_mode="Markdown")


@dp.message()
async def handle_message(message: Message) -> None:
    if not message.text:
        await message.answer("Please send a text message.")
        return
    try:
        data = await api.chat(
            session_id=_session_id(message),
            user_message=message.text,
            user_id=str(message.from_user.id) if message.from_user else None,
        )
        await message.answer(data.get("answer", "Sorry, I had trouble responding."))
    except Exception as exc:  # pragma: no cover - network/runtime guard
        logger.exception("Chat call failed: %s", exc)
        await message.answer(
            "⚠️ I couldn't reach the agent backend. Is the API running?"
        )


async def main() -> None:
    if not settings.telegram_bot_token:
        raise SystemExit(
            "TELEGRAM_BOT_TOKEN is not set. Add it to your .env file."
        )
    bot = Bot(token=settings.telegram_bot_token)
    logger.info("Starting Telegram bot...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
