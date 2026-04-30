from datetime import datetime
from telegram import Bot
from ..db import tasks as tasks_db, users as users_db

_EMOJI = {"oa": "💻", "hirevue": "🎥", "interview": "📞", "application": "📝"}


def _format_task(row) -> str:
    company = row["company"] or "Unknown"
    emoji = _EMOJI.get(row["type"], "📌")
    type_label = row["type"].upper()
    if row["deadline"]:
        dt = row["deadline"] if isinstance(row["deadline"], datetime) else datetime.fromisoformat(row["deadline"])
        days = (dt - datetime.utcnow()).days
        if days < 0:
            deadline_str = f"⚠️ OVERDUE {abs(days)}d ago"
        elif days == 0:
            deadline_str = "🔴 DUE TODAY"
        else:
            deadline_str = f"{days}d remaining"
    else:
        deadline_str = "no deadline"
    return f"{emoji} *{company}* — {type_label} [{deadline_str}]"


async def send_daily_digest(bot: Bot) -> None:
    all_users = users_db.get_all_users()

    for user in all_users:
        if not user["gmail_token_json"]:
            continue

        telegram_id = user["telegram_id"]
        rows = tasks_db.get_incomplete_tasks(telegram_id)

        if not rows:
            continue

        lines = [f"☀️ *Daily Digest — {datetime.utcnow().strftime('%d %b %Y')}*\n"]
        lines += [_format_task(r) for r in rows]
        lines.append("\n_Use /tasks for details or /done <company> to mark complete._")

        try:
            await bot.send_message(
                chat_id=telegram_id,
                text="\n".join(lines),
                parse_mode="Markdown",
            )
        except Exception:
            pass
