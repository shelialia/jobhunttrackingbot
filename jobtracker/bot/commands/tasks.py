from datetime import datetime
from html import escape
from telegram import Update
from telegram.ext import ContextTypes
from ..db import tasks

_EMOJI = {"oa": "💻", "hirevue": "🎥", "interview": "📞"}


async def tasks_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    rows = tasks.get_assessment_tasks(telegram_id)

    if not rows:
        await update.message.reply_text("🎉 No pending assessments or interviews right now!")
        return

    context.user_data["last_tasks"] = [row["id"] for row in rows]
    context.user_data["last_remove_context"] = "tasks"

    lines = ["📋 *Pending Assessments & Interviews*\n"]
    for i, row in enumerate(rows, 1):
        company = escape(row["company"] or "Unknown")
        emoji = _EMOJI.get(row["type"], "📌")
        type_label = escape(row["type"].upper())

        if row["deadline"]:
            dt = row["deadline"] if isinstance(row["deadline"], datetime) else datetime.fromisoformat(row["deadline"])
            days = (dt - datetime.utcnow()).days
            if days < 0:
                day_str = f"⚠️ OVERDUE {abs(days)}d ago"
            elif days == 0:
                day_str = "🔴 DUE TODAY"
            else:
                day_str = f"{days}d remaining"
        else:
            day_str = "no deadline"

        role_line = f"\n   <i>{escape(row['role'])}</i>" if row["role"] else ""
        lines.append(f"{i}. {emoji} <b>{company}</b> - <code>{type_label}</code> [{escape(day_str)}]{role_line}")

    lines[0] = "📋 <b>Pending Assessments & Interviews</b>\n"
    lines.append("\n<i>Use /done &lt;task_number&gt; to mark complete</i>")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")
