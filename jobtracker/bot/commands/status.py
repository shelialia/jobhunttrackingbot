from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from ..db import tasks


def _deadline_label(deadline) -> str:
    if not deadline:
        return "no deadline"
    dt = deadline if isinstance(deadline, datetime) else datetime.fromisoformat(deadline)
    days = (dt - datetime.utcnow()).days
    if days < 0:
        return f"OVERDUE ({abs(days)}d ago)"
    if days == 0:
        return "due TODAY"
    return f"due in {days}d"


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
