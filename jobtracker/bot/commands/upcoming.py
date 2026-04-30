from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from ..db import tasks


async def upcoming(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    rows = tasks.get_upcoming_tasks(telegram_id)

    if not rows:
        await update.message.reply_text("Nothing due in the next 7 days.")
        return

    lines = ["*Due in the next 7 days:*\n"]
    for row in rows:
        dt = datetime.fromisoformat(row["deadline"])
        days = (dt - datetime.utcnow()).days
        tag = "TODAY" if days == 0 else f"in {days}d"
        lines.append(
            f"• *{row['company']}* — {row['type'].upper()} ({tag})\n"
            f"  {row['role'] or ''}"
        )

    await update.message.reply_text("\n\n".join(lines), parse_mode="Markdown")
