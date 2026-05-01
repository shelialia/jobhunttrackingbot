from datetime import datetime
from html import escape
from telegram import Update
from telegram.ext import ContextTypes
from ..db import tasks
from ..message_utils import reply_chunked_lines
from ..time_utils import parse_datetime, relative_day_label

_EMOJI = {"oa": "💻", "hirevue": "🎥", "interview": "📞", "application": "📝"}


def _task_datetime(row) -> datetime:
    raw = row["interview_date"] if row["type"] == "interview" else row["deadline"]
    dt = parse_datetime(raw)
    if dt is None:
        raise ValueError("Missing task datetime")
    return dt


async def upcoming(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    rows = tasks.get_upcoming_tasks(telegram_id)

    if not rows:
        await update.message.reply_text("🎉 Nothing due in the next 7 days!")
        return

    lines = ["📅 <b>Due in the next 7 days:</b>\n"]
    for row in rows:
        _ = _task_datetime(row)
        tag = relative_day_label(
            row["interview_date"] if row["type"] == "interview" else row["deadline"],
            is_deadline=(row["type"] != "interview"),
        )
        emoji = _EMOJI.get(row["type"], "📌")
        role_line = f"\n   <i>{escape(row['role'])}</i>" if row["role"] else ""
        lines.append(
            f"{emoji} <b>{escape(row['company'] or 'Unknown')}</b> - "
            f"<code>{escape(row['type'].upper())}</code> [{escape(tag)}]{role_line}"
        )

    await reply_chunked_lines(update.message, lines, parse_mode="HTML")
