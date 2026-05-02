from telegram import Update
from telegram.ext import ContextTypes
from ..db import users


INTRO_TEXT = (
    "🚀 <b>Welcome to CronJobBot!</b>\n\n"
    "I help turn messy job-search emails into a clean application tracker — "
    "so you never miss a deadline, lose track of where you stand, or forget who ghosted you.\n\n"
    "Here's what I do for you:\n\n"
    "☀️ <b>Daily inbox digest</b> — every morning I scan your Gmail and tell you "
    "what's new: applications submitted, OAs received, interviews scheduled, offers, rejections.\n\n"
    "⏰ <b>Daily reminders</b> — I push your unscheduled interviews, overdue OAs, "
    "and upcoming deadlines straight to your chat. No need to check in.\n\n"
    "✅ <b>Manage action items</b> — view what needs doing, mark things as done, "
    "add tasks manually. Your job hunt to-do list, in Telegram.\n\n"
    "🧭 <b>Track every application</b> — see the full timeline of each company "
    "from application → OA → interview rounds → offer/rejection.\n\n"
    "📊 <b>Visualise your funnel</b> — stats and a Sankey diagram show exactly "
    "where you're losing momentum across your search.\n\n"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id

    if users.get_user(telegram_id):
        await update.message.reply_text(
            INTRO_TEXT + "Type /help to see all commands.",
            parse_mode="HTML",
        )
        return

    context.user_data["awaiting_privacy_confirm"] = True
    await update.message.reply_text(
        INTRO_TEXT +
        "⚠️ <b>Privacy Notice</b>\n\n"
        "This bot reads your Gmail to track job applications automatically. "
        "Relevant emails are processed by an AI model (currently Google Gemini).\n\n"
        "We only scan emails matching job-related subject keywords. "
        "However, we cannot guarantee unrelated emails won't occasionally be processed.\n\n"
        "<b>Do not use this bot if you are uncomfortable with your emails being scanned by an AI.</b>\n\n"
        "By continuing, you acknowledge this and accept the associated risks.\n\n"
        "Type /confirm to continue, or simply stop here.",
        parse_mode="HTML",
    )
