from telegram import Update
from telegram.ext import ContextTypes
from ..db import users, cycles


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    user = users.get_user(telegram_id)

    if not user:
        await update.message.reply_text("Please run /start first.")
        return

    label_arg = " ".join(context.args) if context.args else None

    if label_arg:
        cycle = cycles.get_cycle_by_label(telegram_id, label_arg)
        if not cycle:
            await update.message.reply_text(f"No cycle found with label '{label_arg}'.")
            return
    else:
        cycle = cycles.get_active_cycle(telegram_id)
        if not cycle:
            await update.message.reply_text("No active cycle. Use /newcycle to start one.")
            return

    s = cycles.get_cycle_stats(cycle["id"], telegram_id)
    avg = f"{s['avg_response_days']}d" if s["avg_response_days"] else "N/A"

    text = (
        f"*Stats — {cycle['label']}*\n\n"
        f"Applied: {s['total_applied']}\n"
        f"Response rate: {s['response_rate']}%\n"
        f"Pending tasks: {s['pending']}\n"
        f"Avg response time: {avg}\n"
        f"Apps/week: {s['apps_per_week']}\n"
        f"Completed this week: {s['completed_this_week']}"
    )
    await update.message.reply_text(text, parse_mode="Markdown")
