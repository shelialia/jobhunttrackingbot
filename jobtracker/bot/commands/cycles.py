from telegram import Update
from telegram.ext import ContextTypes
from ..db import users, cycles as cycles_db


async def list_cycles(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    all_cycles = cycles_db.get_all_cycles(telegram_id)

    if not all_cycles:
        await update.message.reply_text("No cycles yet. Use /newcycle to create one.")
        return

    lines = ["*Your cycles:*\n"]
    for c in all_cycles:
        status_tag = "active" if c["status"] == "active" else "closed"
        started = c["started_at"][:10] if c["started_at"] else "?"
        ended = c["ended_at"][:10] if c["ended_at"] else "ongoing"
        lines.append(f"• *{c['label']}* [{status_tag}]\n  {started} → {ended}")

    await update.message.reply_text("\n\n".join(lines), parse_mode="Markdown")


async def new_cycle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    user = users.get_user(telegram_id)

    if not user:
        await update.message.reply_text("Please run /start first.")
        return

    label = " ".join(context.args) if context.args else None
    if not label:
        await update.message.reply_text("Usage: /newcycle <label>\nExample: /newcycle Summer 2025")
        return

    active = cycles_db.get_active_cycle(telegram_id)
    if active:
        cycles_db.close_cycle(active["id"])

    cycle_id = cycles_db.create_cycle(telegram_id, label)
    users.set_active_cycle(telegram_id, cycle_id)

    await update.message.reply_text(
        f"Started new cycle: *{label}*"
        + (f"\nClosed previous cycle: *{active['label']}*" if active else ""),
        parse_mode="Markdown",
    )
