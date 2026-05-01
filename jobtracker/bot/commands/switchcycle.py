from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from ..db import cycles as cycles_db, users as users_db


async def switchcycle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    if not users_db.get_user(telegram_id):
        await update.message.reply_text("Please run /start first.")
        return

    all_cycles = cycles_db.get_all_cycles(telegram_id)
    if not all_cycles:
        await update.message.reply_text("No cycles found. Use /newcycle to create one.")
        return

    keyboard = []
    for cycle in all_cycles:
        dot = "🟢" if cycle["is_active"] else "⚪"
        keyboard.append([
            InlineKeyboardButton(
                f"{dot} {cycle['name']}",
                callback_data=f"switch_cycle:{cycle['id']}",
            )
        ])

    await update.message.reply_text(
        "Select a cycle to switch to:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
