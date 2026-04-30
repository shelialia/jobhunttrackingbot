from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from ..db import users, cycles, tasks


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    user = users.get_user(telegram_id)

    if not user:
        await update.message.reply_text("Please run /start first.")
        return

    # Expected: /add <company> <YYYY-MM-DD> [type]
    args = context.args
    if not args or len(args) < 1:
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

    cycle = cycles.get_active_cycle(telegram_id)
    if not cycle:
        await update.message.reply_text("No active cycle. Use /newcycle first.")
        return

    task_id = tasks.insert_manual_task(
        telegram_id, cycle["id"], company, "", task_type, deadline
    )
    await update.message.reply_text(
        f"Added: *{company}* — {task_type.upper()}"
        + (f", due {deadline[:10]}" if deadline else "")
        + f" (id {task_id})",
        parse_mode="Markdown",
    )
