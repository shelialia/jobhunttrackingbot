from telegram import Update
from telegram.ext import ContextTypes
from ..db import tasks as tasks_db


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /done <task_number>\n\nRun /tasks to see the numbered list.")
        return

    index = int(context.args[0]) - 1
    last_tasks = context.user_data.get("last_tasks", [])

    if not last_tasks or index < 0 or index >= len(last_tasks):
        await update.message.reply_text("❌ Invalid number. Run /tasks first to see the list.")
        return

    task = tasks_db.get_task_by_id(last_tasks[index])
    if not task or task["telegram_id"] != telegram_id:
        await update.message.reply_text("❌ Task not found. Run /tasks to refresh the list.")
        return

    company = task["company"] or "Unknown"
    type_label = task["type"].upper()
    deadline_str = ""
    if task["deadline"]:
        from datetime import datetime
        dt = task["deadline"] if isinstance(task["deadline"], datetime) else datetime.fromisoformat(task["deadline"])
        deadline_str = f", due {dt.strftime('%d %b')}"

    display = f"{company} — {type_label}"
    context.user_data["pending_action"] = {"action": "done", "task_id": task["id"], "display": display}

    await update.message.reply_text(
        f"☑️ Mark *{company}* — {type_label}{deadline_str} as done?\n\nSend /confirm to proceed.",
        parse_mode="Markdown",
    )
