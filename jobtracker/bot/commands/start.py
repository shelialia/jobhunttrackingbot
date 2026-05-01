from telegram import Update
from telegram.ext import ContextTypes
from ..db import users


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id

    if users.get_user(telegram_id):
        await update.message.reply_text(
            "👋 *Welcome back to Job Hunt Tracker!*\n\n"
            "Type /help to see all available commands.",
            parse_mode="Markdown",
        )
        return

    context.user_data["awaiting_privacy_confirm"] = True
    await update.message.reply_text(
        "⚠️ *Privacy Notice*\n\n"
        "This bot reads your Gmail to track job applications automatically. "
        "To do this, relevant emails are processed by an AI model (currently Google Gemini).\n\n"
        "We only scan emails related to job applications based on subject line keywords. "
        "However, we cannot guarantee that unrelated emails won't occasionally be processed.\n\n"
        "Do not use this bot if you are uncomfortable with your emails being scanned by an AI.\n\n"
        "By continuing, you acknowledge this and accept the associated risks.\n\n"
        "Type /confirm to continue, or simply stop here.",
        parse_mode="Markdown",
    )
