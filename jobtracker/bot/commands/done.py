from html import escape
from telegram import Update
from telegram.ext import ContextTypes
from ..db import tasks as tasks_db, users as users_db
from ..time_utils import to_local


def _resolve_task(arg: str, user_data: dict) -> tuple[int | None, str]:
    """Return (task_id, error_message). error_message is empty on success."""
    arg = arg.strip().lower()

    if arg.startswith("i"):
        raw = arg[1:]
        list_key = "last_interview_tasks"
        section = "interview"
    else:
        raw = arg
        list_key = "last_assessment_tasks"
        section = "assessment"

    if not raw.isdigit():
        return None, "Usage: /done &lt;assessment_index&gt; or /done i&lt;interview_index&gt;.\n\nRun /tasks to see the numbered list."

    index = int(raw) - 1
    task_list = user_data.get(list_key, [])

    if not task_list or index < 0 or index >= len(task_list):
        return None, f"❌ No {section} #{raw}. Run /tasks to refresh the list."

    return task_list[index], ""


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text(
            "Usage: /done &lt;assessment_index&gt; or /done i&lt;interview_index&gt;.\n\nRun /tasks to see the numbered list.",
            parse_mode="HTML",
        )
        return

    task_id, error = _resolve_task(context.args[0], context.user_data)
    if error:
        await update.message.reply_text(error, parse_mode="HTML")
        return

    task = tasks_db.get_task_by_id(task_id)
    if not task or task["telegram_id"] != telegram_id:
        await update.message.reply_text("❌ Task not found. Run /tasks to refresh the list.")
        return

    user = users_db.get_user(telegram_id)
    tz_name = user["timezone"] if user and "timezone" in user.keys() else None
    company = task["company"] or "Unknown"
    type_label = task["type"].upper()
    deadline_str = ""
    raw_due = task["interview_date"] if task["type"] == "interview" else task["deadline"]
    due_at = to_local(raw_due, tz_name)
    if due_at:
        deadline_str = f", due {due_at.strftime('%d %b').lstrip('0')}"

    display = f"{company} — {type_label}"
    context.user_data["pending_action"] = {"action": "done", "task_id": task["id"], "display": display}

    await update.message.reply_text(
        f"☑️ Mark <b>{escape(company)}</b> — {escape(type_label)}{escape(deadline_str)} as done?\n\nSend /confirm to proceed.",
        parse_mode="HTML",
    )
