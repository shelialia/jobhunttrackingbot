from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from ..db import users, tasks


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    user = users.get_user(telegram_id)

    if not user:
        await update.message.reply_text("Please run /start first.")
        return

    args = context.args
    if not args:
        await update.message.reply_text(
            "Usage: /add <company> [YYYY-MM-DD] [oa|hirevue|interview|application]\n"
            "Example: /add Stripe 2025-06-01 oa"
        )
        return

    company = args[0]
    deadline = None
    task_type = "application"

    for arg in args[1:]:
        if arg in ("oa", "hirevue", "interview", "application"):
            task_type = arg
        else:
            try:
                datetime.strptime(arg, "%Y-%m-%d")
                deadline = arg + "T23:59:00"
            except ValueError:
                pass

    task_id = tasks.insert_manual_task(telegram_id, company, "", task_type, deadline)
    await update.message.reply_text(
        f"➕ Added: *{company}* — {task_type.upper()}"
        + (f", due {deadline[:10]}" if deadline else "")
        + "!",
        parse_mode="Markdown",
    )
