from html import escape
from telegram import Update
from telegram.ext import ContextTypes
from ..db import tasks
from ..message_utils import reply_chunked_lines
from ..time_utils import relative_day_label

_EMOJI = {"oa": "💻", "hirevue": "🎥", "interview": "📞"}


def _task_status_label(row) -> str:
    if row["type"] == "interview":
        return relative_day_label(row["interview_date"], is_deadline=False)

    if row["deadline"]:
        return relative_day_label(row["deadline"], is_deadline=True)

    return "no deadline"


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
        day_str = _task_status_label(row)

        role_line = f"\n   <i>{escape(row['role'])}</i>" if row["role"] else ""
        lines.append(f"{i}. {emoji} <b>{company}</b> - <code>{type_label}</code> [{escape(day_str)}]{role_line}")

    lines[0] = "📋 <b>Pending Assessments & Interviews</b>\n"
    lines.append("\n<i>Use /done &lt;task_number&gt; to mark complete</i>")
    await reply_chunked_lines(update.message, lines, parse_mode="HTML")
