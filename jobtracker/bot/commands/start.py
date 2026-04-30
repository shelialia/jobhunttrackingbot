from telegram import Update
from telegram.ext import ContextTypes
from ..db import users, cycles


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    users.create_user(telegram_id)

    existing_cycle = cycles.get_active_cycle(telegram_id)
    if not existing_cycle:
        cycle_id = cycles.create_cycle(telegram_id, "My Job Hunt")
        users.set_active_cycle(telegram_id, cycle_id)

    await update.message.reply_text(
        "Welcome to Job Hunt Tracker!\n\n"
        "I'll monitor your Gmail inbox for job application tasks — "
        "OAs, HireVues, interviews — and send you daily digests and deadline nudges.\n\n"
        "To get started, connect your Gmail account:\n"
        "/connect\n\n"
        "Type /help to see all commands."
    )
