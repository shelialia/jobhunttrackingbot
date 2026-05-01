from telegram import Update
from telegram.ext import ContextTypes
from ..db import users as users_db


async def newcycle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    if not users_db.get_user(telegram_id):
        await update.message.reply_text("Please run /start first.")
        return

    context.user_data["awaiting_cycle_name"] = "newcycle"
    await update.message.reply_text(
        "What would you like to name your new cycle?\n"
        '_(e.g. "Summer 2025", "Full Time 2026")_',
        parse_mode="Markdown",
    )
