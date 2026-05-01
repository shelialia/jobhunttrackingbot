from telegram import Update
from telegram.ext import ContextTypes
from ..db import cycles as cycles_db, users as users_db


async def endcycle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    if not users_db.get_user(telegram_id):
        await update.message.reply_text("Please run /start first.")
        return

    cycle = cycles_db.get_active_cycle(telegram_id)
    if not cycle:
        await update.message.reply_text(
            "No active cycle. Use /newcycle to create one, or /cycles to view existing ones."
        )
        return

    cycles_db.end_cycle(cycle["id"])
    await update.message.reply_text(
        f'⏹ *"{cycle["name"]}"* has ended.\n\n'
        "Use /newcycle to start a new cycle, or /cycles to switch to an existing one.",
        parse_mode="Markdown",
    )
