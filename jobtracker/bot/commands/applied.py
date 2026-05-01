from datetime import datetime
from html import escape
from telegram import Update
from telegram.ext import ContextTypes
from ..db import cycles as cycles_db, tasks, users

_STATUS_EMOJI = {"done": "✅", "offer": "🎉", "reject": "❌", "rejected": "❌"}


async def applied(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    if not users.get_user(telegram_id):
        await update.message.reply_text("Please run /start first.")
        return

    cycle = cycles_db.get_active_cycle(telegram_id)
    if not cycle:
        await update.message.reply_text(
            "No active cycle. Use /newcycle to create one, or /cycles to switch to an existing one."
        )
        return

    rows = tasks.get_cycle_applications(telegram_id, cycle["id"])

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
        company = escape(row["company"] or "Unknown")
        role = escape(row["role"] or "")
        raw_date = row["email_date"] or row["created_at"]
        dt = raw_date if isinstance(raw_date, datetime) else datetime.fromisoformat(raw_date)
        date_str = dt.strftime("%d %b")
        role_part = f" - <i>{role}</i>" if role else ""
        status_emoji = _STATUS_EMOJI.get(row["status"], "")
        prefix = f"{status_emoji} " if status_emoji else ""
        lines.append(f"{i}. {prefix}<b>{company}</b>{role_part} <i>(applied {escape(date_str)})</i>")

    lines[0] = f"📝 <b>Applications Submitted</b> ({len(rows)} total)\n"
    lines.append("\n<i>Use /offer &lt;app_number&gt; or /reject &lt;app_number&gt; to update status</i>")
    lines.append("<i>Use /timeline &lt;number&gt; to see full progress</i>")
    lines.append("<i>e.g. /timeline 1</i>")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")
