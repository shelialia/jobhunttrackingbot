from telegram import Update
from telegram.ext import ContextTypes
from ..db import users


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id

    if users.get_user(telegram_id):
        await update.message.reply_text(
            "🔥 *Welcome back!*\n\n"
            "Good to see you again. Here's what you can do:\n\n"
            "📬 /scan — Scan your inbox for new updates\n"
            "📋 /applied — View your applications\n"
            "📊 /stats — See your job search stats\n"
            "🔀 /sankey — Visualise your application funnel\n"
            "⏰ /deadlines — Check upcoming OA deadlines\n"
            "🔗 /connect — Reconnect your Gmail\n\n"
            "Type /help to see all commands.",
            parse_mode="Markdown",
        )
        return

    context.user_data["awaiting_privacy_confirm"] = True
    await update.message.reply_text(
        "🚀 *Welcome to CronJobBot!*\n\n"
        "Your personal job search tracker — automated, so you can focus on the grind.\n\n"
        "Here's what I do:\n"
        "📬 *Auto-track applications* — I scan your Gmail and automatically log every application, OA, HireVue, and interview\n"
        "🔔 *Remind you of deadlines* — never miss an OA deadline or forget to follow up\n"
        "👻 *Detect ghosted apps* — I flag companies that have gone silent so you know where you stand\n"
        "📊 *Show your stats* — response rates, interview depth, offer rate, and a Sankey funnel of your job search\n\n"
        "All automatically. No manual logging.\n\n"
        "⚠️ *Privacy Notice*\n\n"
        "This bot reads your Gmail to track job applications automatically. "
        "Relevant emails are processed by an AI model (currently Google Gemini).\n\n"
        "We only scan emails matching job-related subject keywords. "
        "However, we cannot guarantee unrelated emails won't occasionally be processed.\n\n"
        "*Do not use this bot if you are uncomfortable with your emails being scanned by an AI.*\n\n"
        "By continuing, you acknowledge this and accept the associated risks.\n\n"
        "Type /confirm to continue, or simply stop here.",
        parse_mode="Markdown",
    )
