from telegram import Update
from telegram.ext import ContextTypes
from ..db import users


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id

    if users.get_user(telegram_id):
        await update.message.reply_text(
            "🔥 <b>Welcome back!</b>\n\n"
            "Useful shortcuts:\n\n"
            "📬 /scan — Scan Gmail for new application updates\n"
            "📋 /tasks — See pending assessments and interviews\n"
            "📝 /applied — View tracked applications\n"
            "🧭 /timeline &lt;app_number&gt; — See one application's full chain\n"
            "📊 /stats — Check active-cycle stats\n"
            "🔀 /sankey — Export your funnel diagram\n"
            "🔗 /connect — Reconnect Gmail\n\n"
            "Type /help to see all commands.",
            parse_mode="HTML",
        )
        return

    context.user_data["awaiting_privacy_confirm"] = True
    await update.message.reply_text(
        "🚀 <b>Welcome to CronJobBot!</b>\n\n"
        "I help turn messy job-search emails into a clean application tracker.\n\n"
        "Most useful things I can do:\n"
        "📬 <b>Scan Gmail</b> for application confirmations, OAs, HireVues, interviews, offers, and rejections\n"
        "🧩 <b>Link every update</b> into one application chain, even when the original application email is missing\n"
        "📋 <b>Track action items</b> like unscheduled interviews, overdue assessments, and upcoming deadlines\n"
        "🧭 <b>Show timelines</b> for each company, including interview rounds and confirmed dates\n"
        "📊 <b>Summarise your funnel</b> with stats and a Sankey diagram\n\n"
        "You can still add or remove items manually when the scan gets something wrong.\n\n"
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
