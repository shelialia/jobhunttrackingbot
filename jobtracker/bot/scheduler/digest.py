from datetime import datetime
from telegram import Bot
from ..db import tasks as tasks_db, users as users_db


def _format_task(row) -> str:
    company = row["company"] or "Unknown"
    task_type = row["type"].upper()
    if row["deadline"]:
        try:
            dt = datetime.fromisoformat(row["deadline"])
            days = (dt - datetime.utcnow()).days
            if days < 0:
                deadline_str = f"OVERDUE ({abs(days)}d ago)"
            elif days == 0:
                deadline_str = "due TODAY"
            else:
                deadline_str = f"due in {days}d"
        except ValueError:
            deadline_str = row["deadline"][:10]
    else:
        deadline_str = "no deadline"

    return f"• {company} — {task_type} ({deadline_str})"


async def send_daily_digest(bot: Bot) -> None:
    all_users = users_db.get_all_users()

    for user in all_users:
        if not user["gmail_token_json"]:
            continue

        telegram_id = user["telegram_id"]
        rows = tasks_db.get_incomplete_tasks(telegram_id)

        if not rows:
            continue

        lines = [f"*Daily digest — {datetime.utcnow().strftime('%Y-%m-%d')}*\n"]
        lines += [_format_task(r) for r in rows]
        lines.append("\nUse /status for full details or /done <company> to mark complete.")

        try:
            await bot.send_message(
                chat_id=telegram_id,
                text="\n".join(lines),
                parse_mode="Markdown",
            )
        except Exception:
            pass
