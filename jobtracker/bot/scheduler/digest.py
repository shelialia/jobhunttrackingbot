from datetime import datetime
from telegram import Bot
from ..db import tasks as tasks_db, users as users_db

_TASK_EMOJI = {"oa": "💻", "hirevue": "🎥", "interview": "📞"}


def _format_application(row) -> str:
    company = row["company"] or "Unknown"
    role = f" — {row['role']}" if row["role"] else ""
    return f"📝 *{company}*{role}"


def _format_task(row) -> str:
    company = row["company"] or "Unknown"
    emoji = _TASK_EMOJI.get(row["type"], "📌")
    type_label = row["type"].upper()
    role = f" — {row['role']}" if row["role"] else ""
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
    return f"{emoji} *{company}*{role} — {type_label} [{deadline_str}]"


async def send_daily_digest(bot: Bot) -> None:
    all_users = users_db.get_all_users()

    for user in all_users:
        if not user["gmail_token_json"]:
            continue

        telegram_id = user["telegram_id"]
        applications = tasks_db.get_applications_by_status(telegram_id, "incomplete")
        tasks = tasks_db.get_assessment_tasks(telegram_id)
        offers = tasks_db.get_applications_by_status(telegram_id, "offer")
        rejections = tasks_db.get_applications_by_status(telegram_id, "rejected")

        if not applications and not tasks and not offers and not rejections:
            continue

        lines = [f"☀️ *Daily Digest — {datetime.utcnow().strftime('%d %b %Y')}*\n"]
        sections = [
            ("📝 Applications Submitted", applications, _format_application),
            ("🎯 Interviews & Assessments", tasks, _format_task),
            ("🎉 Offers", offers, _format_application),
            ("❌ Rejections", rejections, _format_application),
        ]

        for title, rows, formatter in sections:
            if not rows:
                continue
            lines.append(f"{title} ({len(rows)})")
            lines.extend(formatter(row) for row in rows)
            lines.append("")

        lines.append("_Use /tasks for details or /done <task_number> to mark complete._")

        try:
            await bot.send_message(
                chat_id=telegram_id,
                text="\n".join(lines),
                parse_mode="Markdown",
            )
        except Exception:
            pass
