from html import escape
from datetime import datetime
from telegram import Bot
from ..db import tasks as tasks_db, users as users_db

_TASK_EMOJI = {"oa": "💻", "hirevue": "🎥", "interview": "📞"}


def _format_application(row) -> str:
    company = escape(row["company"] or "Unknown")
    role = escape(row["role"]) if row["role"] else ""
    parts = [f"• <b>{company}</b>"]
    if role:
        parts.append(f" <i>{role}</i>")
    return "".join(parts)


def _format_task(row) -> str:
    company = escape(row["company"] or "Unknown")
    emoji = _TASK_EMOJI.get(row["type"], "📌")
    type_label = escape(row["type"].upper())
    role = escape(row["role"]) if row["role"] else ""
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

    parts = [f"• {emoji} <b>{company}</b>"]
    if role:
        parts.append(f" <i>{role}</i>")
    parts.append(f" <code>{type_label}</code>")
    parts.append(f" <i>{escape(deadline_str)}</i>")
    return "".join(parts)


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

        lines = [f"☀️ <b>Daily Digest</b> <code>{datetime.utcnow().strftime('%d %b %Y')}</code>", ""]
        primary_sections = [
            ("📝 Applications Submitted", applications, _format_application),
            ("🎯 Pending Tasks", tasks, _format_task),
        ]

        for title, rows, formatter in primary_sections:
            lines.append(f"<u><b>{escape(title)}</b></u> <b>({len(rows)})</b>")
            lines.extend(formatter(row) for row in rows)
            lines.append("")

        for title, rows, formatter in (
            ("🎉 Offers", offers, _format_application),
            ("❌ Rejections", rejections, _format_application),
        ):
            if not rows:
                continue
            lines.append(f"<u><b>{escape(title)}</b></u> <b>({len(rows)})</b>")
            lines.extend(formatter(row) for row in rows)
            lines.append("")

        lines.append("<i>Use /tasks for details or /done &lt;task_number&gt; to mark complete.</i>")

        try:
            await bot.send_message(
                chat_id=telegram_id,
                text="\n".join(lines),
                parse_mode="HTML",
            )
        except Exception:
            pass
