from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from ..db import cycles as cycles_db, users as users_db


async def cycles_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    user = users_db.get_user(telegram_id)
    if not user:
        await update.message.reply_text("Please run /start first.")
        return

    all_cycles = cycles_db.get_all_cycles(telegram_id)
    if not all_cycles:
        await update.message.reply_text("No cycles yet. Use /newcycle to create one.")
        return

    lines = ["*Your cycles:*\n"]
    for cycle in all_cycles:
        summary = cycles_db.get_cycle_summary(telegram_id, cycle["id"])
        dot = "🟢" if cycle["is_active"] else "⚪"
        label = " (active)" if cycle["is_active"] else " (ended)"
        lines.append(f"{dot} *{cycle['name']}*{label}")
        lines.append(f"   {summary['apps']} apps · {summary['interviews']} interviews")
        if summary["offers"]:
            lines[-1] += f" · {summary['offers']} offer(s)"
        lines.append("")

    keyboard = [[InlineKeyboardButton("＋ New Cycle", callback_data="cycle_action:new")]]
    await update.message.reply_text(
        "\n".join(lines).strip(),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
