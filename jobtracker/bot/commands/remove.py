from telegram import Update
from telegram.ext import ContextTypes
from ..db import tasks as tasks_db


async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id

    last_ctx = context.user_data.get("last_remove_context")
    if last_ctx == "applied":
        param_hint = "<app_number>"
    elif last_ctx == "tasks":
        param_hint = "<task_number>"
    else:
        param_hint = "<app_number> or <task_number>"

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(f"Usage: /remove {param_hint}\n\nRun /tasks or /applied first to see the numbered list.")
        return

    index = int(context.args[0]) - 1
    remove_context = context.user_data.get("last_remove_context", "tasks")
    id_list = context.user_data.get(f"last_{remove_context}", [])

    if not id_list or index < 0 or index >= len(id_list):
        await update.message.reply_text("❌ Invalid number. Run /tasks or /applied first to see the list.")
        return

    task = tasks_db.get_task_by_id(id_list[index])
    if not task or task["telegram_id"] != telegram_id:
        await update.message.reply_text("❌ Task not found. Refresh with /tasks or /applied.")
        return

    company = task["company"] or "Unknown"
    type_label = task["type"].upper()
    display = f"{company} — {type_label}"
    context.user_data["pending_action"] = {"action": "remove", "task_id": task["id"], "display": display}

    await update.message.reply_text(
        f"🗑️ Remove *{company}* — {type_label} from your list?\n\nSend /confirm to proceed.",
        parse_mode="Markdown",
    )
