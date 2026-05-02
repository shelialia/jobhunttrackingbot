from html import escape
from telegram import Update
from telegram.ext import ContextTypes
from ..db import tasks as tasks_db


def _usage_hint(last_ctx: str | None) -> str:
    if last_ctx == "applied":
        return "/remove &lt;app_index&gt;"
    if last_ctx == "tasks":
        return "/remove &lt;assessment_index&gt; or /remove i&lt;interview_index&gt;"
    return "/remove &lt;app_index&gt;, /remove &lt;assessment_index&gt;, or /remove i&lt;interview_index&gt;"


def _resolve_remove_target(arg: str, user_data: dict) -> tuple[int | None, str]:
    last_ctx = user_data.get("last_remove_context")
    arg = arg.strip().lower()

    if last_ctx == "applied":
        if not arg.isdigit():
            return None, "Usage: /remove &lt;app_index&gt;\n\nRun /applied first to see the numbered list."
        id_list = user_data.get("last_applied", [])
        label = "application"
        raw = arg
    else:
        if arg.startswith("i"):
            raw = arg[1:]
            id_list = user_data.get("last_interview_tasks", [])
            label = "interview"
        else:
            raw = arg
            id_list = user_data.get("last_assessment_tasks", [])
            label = "assessment"

        if not raw.isdigit():
            return None, f"Usage: {_usage_hint(last_ctx)}\n\nRun /tasks or /applied first to see the numbered list."

    index = int(raw) - 1
    if not id_list or index < 0 or index >= len(id_list):
        return None, f"❌ No {label} #{raw}. Run /tasks or /applied to refresh the list."

    return id_list[index], ""


async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id

    last_ctx = context.user_data.get("last_remove_context")
    if not context.args:
        await update.message.reply_text(
            f"Usage: {_usage_hint(last_ctx)}\n\nRun /tasks or /applied first to see the numbered list.",
            parse_mode="HTML",
        )
        return

    task_id, error = _resolve_remove_target(context.args[0], context.user_data)
    if error:
        await update.message.reply_text(error, parse_mode="HTML")
        return

    task = tasks_db.get_task_by_id(task_id)
    if not task or task["telegram_id"] != telegram_id:
        await update.message.reply_text("❌ Task not found. Refresh with /tasks or /applied.")
        return

    company = task["company"] or "Unknown"
    type_label = task["type"].upper()
    display = f"{company} — {type_label}"
    context.user_data["pending_action"] = {"action": "remove", "task_id": task["id"], "display": display}

    await update.message.reply_text(
        f"🗑️ Remove <b>{escape(company)}</b> — {escape(type_label)} from your list?\n\nSend /confirm to proceed.",
        parse_mode="HTML",
    )
