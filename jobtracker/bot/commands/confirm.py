from telegram import Update
from telegram.ext import ContextTypes
from ..db import tasks as tasks_db
from ..db import users as users_db

_STATUS_MESSAGES = {
    "done":   ("✅", "marked as *done*"),
    "offer":  ("🎉", "marked as an *offer* — congratulations!"),
    "rejected": ("❌", "marked as *rejected*"),
    "remove": ("🗑️", "removed"),
}


async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.user_data.get("awaiting_privacy_confirm"):
        context.user_data.pop("awaiting_privacy_confirm")
        users_db.create_user(update.effective_user.id)
        context.user_data["awaiting_cycle_name"] = "onboarding"
        await update.message.reply_text(
            "Great! Let's set up your first job search cycle.\n\n"
            "What would you like to name it?\n"
            '_(e.g. "Summer 2025 Internship", "Full Time Grad 2026")_',
            parse_mode="Markdown",
        )
        return

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
