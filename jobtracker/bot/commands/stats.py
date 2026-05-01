from html import escape
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
        f"\n"
        f"{'Response rate:':<20} {s['response_rate']:>3}%\n"
        f"{'Offer rate:':<20} {s['offer_rate']:>5}%\n"
        f"{'Avg days to reply:':<20} {s['avg_days']:>4}"
    )

    leaderboard_lines = []
    outcome_labels = {
        "offer": "Offer 🎉",
        "rejected": "Rejected 😭",
        "ongoing": "Ongoing 👀",
    }
    for idx, row in enumerate(s["round_leaderboard"], 1):
        leaderboard_lines.append(
            f"{idx}. {row['company']:<18} {row['rounds']} rounds → {outcome_labels[row['outcome']]}"
        )
    if not leaderboard_lines:
        leaderboard_lines.append("No interview chains yet")

    bucket_lines = [
        f"{label:<12} {count:>3}"
        for label, count in (
            ("1 round", s["interview_depth_buckets"]["1 round"]),
            ("2-3 rounds", s["interview_depth_buckets"]["2-3 rounds"]),
            ("4+ rounds", s["interview_depth_buckets"]["4+ rounds"]),
        )
    ]

    await update.message.reply_text(
        (
            f"📊 <b>{escape(cycle['name'])}</b>\n\n"
            f"<pre>{escape(table)}</pre>\n"
            f"💀 <b>Total interview rounds suffered:</b> {s['total_interview_rounds']}\n\n"
            f"🏆 <b>Most Rounds Survived</b>\n"
            f"────────────────────────\n"
            f"<pre>{escape(chr(10).join(leaderboard_lines))}</pre>\n"
            f"📊 <b>Interview Depth</b>\n"
            f"───────────────────\n"
            f"<pre>{escape(chr(10).join(bucket_lines))}</pre>"
        ),
        parse_mode="HTML",
    )
