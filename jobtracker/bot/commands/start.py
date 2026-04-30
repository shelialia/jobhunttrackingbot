from telegram import Update
from telegram.ext import ContextTypes
from ..db import users


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    users.create_user(telegram_id)

    await update.message.reply_text(
        "👋 *Welcome to Job Hunt Tracker!*\n\n"
        "I monitor your Gmail inbox for job application tasks — "
        "OAs, HireVues, interviews — and help you stay on top of deadlines.\n\n"
        "🔗 To get started, connect your Gmail:\n"
        "/connect\n\n"
        "Type /help to see all available commands.",
        parse_mode="Markdown",
    )
