from telegram import Update
from telegram.ext import ContextTypes
from ..db import tasks as tasks_db

_STATUS_MESSAGES = {
    "done":   ("✅", "marked as *done*"),
    "offer":  ("🎉", "marked as an *offer* — congratulations!"),
    "reject": ("❌", "marked as *rejected*"),
    "remove": ("🗑️", "removed"),
}


async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pending = context.user_data.get("pending_action")

    if not pending:
        await update.message.reply_text("Nothing to confirm. Run a command first.")
        return

    action = pending["action"]
    task_id = pending["task_id"]
    display = pending["display"]

    if action == "remove":
        tasks_db.delete_task(task_id)
    else:
        tasks_db.mark_status(task_id, action)

    context.user_data.pop("pending_action")

    emoji, verb = _STATUS_MESSAGES[action]
    await update.message.reply_text(
        f"{emoji} *{display}* has been {verb}.",
        parse_mode="Markdown",
    )
