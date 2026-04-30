from telegram import Update
from telegram.ext import ContextTypes
from ..db import tasks


async def remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text("Usage: /remove <company name>")
        return

    company = " ".join(context.args)
    task = tasks.find_task_by_company(telegram_id, company)

    if not task:
        await update.message.reply_text(
            f"No pending task found for '{company}'."
        )
        return

    tasks.delete_task(task["id"])
    await update.message.reply_text(
        f"Removed: *{task['company']}* — {task['type'].upper()}",
        parse_mode="Markdown",
    )
