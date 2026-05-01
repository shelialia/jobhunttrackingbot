from telegram import Update
from telegram.ext import ContextTypes
from ..db import tasks as tasks_db


async def reject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /reject <app_number>\n\nRun /applied to see the numbered list.")
        return

    index = int(context.args[0]) - 1
    last_applied = context.user_data.get("last_applied", [])

    if not last_applied or index < 0 or index >= len(last_applied):
        await update.message.reply_text("❌ Invalid number. Run /applied first to see the list.")
        return

    task = tasks_db.get_task_by_id(last_applied[index])
    if not task or task["telegram_id"] != telegram_id:
        await update.message.reply_text("❌ Application not found. Run /applied to refresh the list.")
        return

    company = task["company"] or "Unknown"
    role_str = f" ({task['role']})" if task["role"] else ""
    display = f"{company}{role_str}"
    context.user_data["pending_action"] = {"action": "rejected", "task_id": task["id"], "display": display}

    await update.message.reply_text(
        f"❌ Mark *{company}*{role_str} as *rejected*?\n\nSend /confirm to proceed.",
        parse_mode="Markdown",
    )
