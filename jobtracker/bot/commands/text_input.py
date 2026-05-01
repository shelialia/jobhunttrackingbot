from telegram import Update
from telegram.ext import ContextTypes
from ..db import cycles as cycles_db


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = context.user_data.get("awaiting_cycle_name")
    if not state:
        return

    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Please enter a name for the cycle.")
        return

    telegram_id = update.effective_user.id
    context.user_data.pop("awaiting_cycle_name")
    cycles_db.create_cycle(telegram_id, name)

    if state == "onboarding":
        await update.message.reply_text(
            f'✅ Cycle *"{name}"* created!\n\n'
            "👋 *Welcome to CronJobBot!*\n\n"
            "I monitor your Gmail inbox for job application tasks — "
            "OAs, HireVues, interviews — and help you stay on top of deadlines.\n\n"
            "🔗 Connect your Gmail to get started:\n/connect\n\n"
            "Type /help to see all available commands.",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            f'✅ *"{name}"* is now your active cycle.\n\n'
            "All new tasks from /scan will be tracked here.",
            parse_mode="Markdown",
        )
