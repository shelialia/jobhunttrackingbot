from telegram import Update
from telegram.ext import ContextTypes
from ..db import tasks as tasks_db, cycles as cycles_db, users


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    if not users.get_user(telegram_id):
        await update.message.reply_text("Please run /start first.")
        return

    cycle = cycles_db.get_active_cycle(telegram_id)
    if not cycle:
        await update.message.reply_text(
            "No active cycle. Use /newcycle to create one, or /cycles to switch to an existing one."
        )
        return

    s = tasks_db.get_cycle_stats(telegram_id, cycle["id"])

    table = (
        f"{'Applied':<16} {s['applied']:>4}\n"
        f"{'Interviewing':<16} {s['interviewing']:>4}\n"
        f"{'Offered':<16} {s['offered']:>4}\n"
        f"{'Rejected':<16} {s['rejected']:>4}\n"
        f"{'Ghosted':<16} {s['ghosted']:>4}\n"
        f"{'Pending':<16} {s['pending']:>4}\n"
        f"\n"
        f"{'Response rate:':<20} {s['response_rate']:>3}%\n"
        f"{'Offer rate:':<20} {s['offer_rate']:>5}%\n"
        f"{'Avg days to reply:':<20} {s['avg_days']:>4}"
    )

    await update.message.reply_text(
        f"📊 *{cycle['name']}*\n\n```\n{table}\n```",
        parse_mode="Markdown",
    )
