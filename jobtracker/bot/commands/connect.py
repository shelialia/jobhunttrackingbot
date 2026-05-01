from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from ..db import users
from ..gmail.auth import get_auth_url


async def connect(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    user = users.get_user(telegram_id)

    if not user:
        await update.message.reply_text("Please run /start first.")
        return

    if user["gmail_token_json"]:
        await update.message.reply_text(
            "✅ Your Gmail is already connected!\n\n"
            "Use /scan to trigger a manual inbox check."
        )
        return

    auth_url = get_auth_url(telegram_id)
    keyboard = [[InlineKeyboardButton("🔗 Connect Gmail", url=auth_url)]]
    await update.message.reply_text(
        "📬 *Connect your Gmail account*\n\n"
        "Tap the button below to authorise Gmail access.\n"
        "After authorising, use /scan to do your first inbox scan.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
