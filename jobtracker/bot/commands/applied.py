from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from ..db import tasks

_STATUS_EMOJI = {"done": "✅", "offer": "🎉", "reject": "❌"}


async def applied(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    rows = tasks.get_applications(telegram_id)

    if not rows:
        await update.message.reply_text(
            "📭 No applications tracked yet.\n\n"
            "Use /scan to check your inbox or /add to add one manually."
        )
        return

    context.user_data["last_applied"] = [row["id"] for row in rows]
    context.user_data["last_remove_context"] = "applied"

    lines = [f"📝 *Applications Submitted* ({len(rows)} total)\n"]
    for i, row in enumerate(rows, 1):
        company = row["company"] or "Unknown"
        role = row["role"] or ""
        raw_date = row["email_date"] or row["created_at"]
        dt = raw_date if isinstance(raw_date, datetime) else datetime.fromisoformat(raw_date)
        date_str = dt.strftime("%d %b")
        role_part = f" — _{role}_" if role else ""
        status_emoji = _STATUS_EMOJI.get(row["status"], "")
        prefix = f"{status_emoji} " if status_emoji else ""
        lines.append(f"{i}. {prefix}*{company}*{role_part} _(applied {date_str})_")

    lines.append("\n_Use /offer <app_number> or /reject <app_number> to update status_")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
