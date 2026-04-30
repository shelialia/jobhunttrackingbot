from telegram import Update
from telegram.ext import ContextTypes
from ..db import tasks as tasks_db, users


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    user = users.get_user(telegram_id)

    if not user:
        await update.message.reply_text("Please run /start first.")
        return

    s = tasks_db.get_user_stats(telegram_id)

    await update.message.reply_text(
        "📊 *Your Job Hunt Stats*\n\n"
        f"📝 Total applied: *{s['total']}*\n"
        f"💬 Response rate: *{s['response_rate']}%*\n"
        f"🎉 Offer rate: *{s['offer_rate']}%*\n\n"
        f"📅 This week: *{s['this_week']}* application(s)\n"
        f"🗓️ This month: *{s['this_month']}* application(s)\n\n"
        f"⏳ Pending tasks: *{s['pending']}*",
        parse_mode="Markdown",
    )
