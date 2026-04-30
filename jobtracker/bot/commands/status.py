from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from ..db import tasks


def _deadline_label(deadline_str: str | None) -> str:
    if not deadline_str:
        return "no deadline"
    try:
        dt = datetime.fromisoformat(deadline_str)
        days = (dt - datetime.utcnow()).days
        if days < 0:
            return f"OVERDUE ({abs(days)}d ago)"
        if days == 0:
            return "due TODAY"
        return f"due in {days}d"
    except ValueError:
        return deadline_str


def _type_emoji(task_type: str) -> str:
    return {"interview": "🎤", "hirevue": "🎥", "oa": "💻", "application": "📄"}.get(task_type, "📋")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    rows = tasks.get_incomplete_tasks(telegram_id)

    if not rows:
        await update.message.reply_text("No pending tasks.")
        return

    lines = ["*Pending tasks:*\n"]
    for row in rows:
        emoji = _type_emoji(row["type"])
        label = _deadline_label(row["deadline"])
        company = row["company"] or "Unknown"
        role = row["role"] or ""
        lines.append(f"{emoji} *{company}* — {row['type'].upper()}\n  {role}\n  {label}")

    await update.message.reply_text("\n\n".join(lines), parse_mode="Markdown")
