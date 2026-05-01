from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from ..db import tasks as tasks_db, cycles as cycles_db, users
from ..message_utils import reply_chunked_lines


def _escape_codeblock(text: str) -> str:
    return text.replace("\\", "\\\\").replace("`", "\\`")


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

    lines = [
        f"📊 {cycle['name']}",
        "──────────────────────────────────────────",
        f"{'Applied':<16} {s['applied']:>4}",
        f"{'Interviewing':<16} {s['interviewing']:>4}",
        f"{'Offered':<16} {s['offered']:>4}",
        f"{'Rejected':<16} {s['rejected']:>4}",
        f"{'Ghosted':<16} {s['ghosted']:>4}",
        "",
        f"{'Response rate:':<20} {s['response_rate']:>3}%",
        f"{'Offer rate:':<20} {s['offer_rate']:>5}%",
        f"{'Avg days to reply:':<20} {s['avg_days']:>4}",
    ]

    stats_content = _escape_codeblock("\n".join(lines))
    await reply_chunked_lines(
        update.message,
        stats_content.split("\n"),
        parse_mode=ParseMode.MARKDOWN_V2,
        prefix="```stats\n",
        suffix="\n```",
    )
