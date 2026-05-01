from telegram import Update
from telegram.ext import ContextTypes
from ..db import users


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id

    if users.get_user(telegram_id):
        await update.message.reply_text(
            "🔥 *Welcome back to CronJobBot!* 🔥\n\n"
            "Let's get back to it — your dream job isn't going to land itself! 💪\n\n"
            "I monitor your Gmail inbox for job application tasks — "
            "OAs, HireVues, interviews — and help you stay on top of deadlines.\n\n"
            "🔗 Connect or reconnect your Gmail: /connect\n"
            "📋 View pending tasks: /tasks\n"
            "📊 See your stats: /stats\n\n"
            "Type /help to see all available commands.",
            parse_mode="Markdown",
        )
        return

    context.user_data["awaiting_privacy_confirm"] = True
    await update.message.reply_text(
        "🔥 *Welcome to CronJobBot!* 🚀\n\n"
        "Your job hunt just got a whole lot easier! 🎯\n\n"
        "I monitor your Gmail inbox for job application tasks — "
        "OAs, HireVues, interviews — and help you stay on top of deadlines.\n\n"
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
