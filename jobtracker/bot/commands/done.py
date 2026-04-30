from telegram import Update
from telegram.ext import ContextTypes
from ..db import tasks


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text("Usage: /done <company name>")
        return

    company = " ".join(context.args)
    task = tasks.find_task_by_company(telegram_id, company)

    if not task:
        await update.message.reply_text(
            f"No pending task found for '{company}'. Check /status for exact names."
        )
        return

    tasks.mark_done(task["id"])
    await update.message.reply_text(
        f"Marked *{task['company']}* — {task['type'].upper()} as done.",
        parse_mode="Markdown",
    )
