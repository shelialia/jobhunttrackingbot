from datetime import datetime
from html import escape
from telegram import Update
from telegram.ext import ContextTypes
from ..db import tasks

_EMOJI = {"oa": "💻", "hirevue": "🎥", "interview": "📞", "application": "📝"}


async def upcoming(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    rows = tasks.get_upcoming_tasks(telegram_id)

    if not rows:
        await update.message.reply_text("🎉 Nothing due in the next 7 days!")
        return

    lines = ["📅 <b>Due in the next 7 days:</b>\n"]
    for row in rows:
        dt = row["deadline"] if isinstance(row["deadline"], datetime) else datetime.fromisoformat(row["deadline"])
        days = (dt - datetime.utcnow()).days
        tag = "🔴 TODAY" if days == 0 else f"{days}d"
        emoji = _EMOJI.get(row["type"], "📌")
        role_line = f"\n   <i>{escape(row['role'])}</i>" if row["role"] else ""
        lines.append(
            f"{emoji} <b>{escape(row['company'] or 'Unknown')}</b> - "
            f"<code>{escape(row['type'].upper())}</code> [{escape(tag)}]{role_line}"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")
