from html import escape
from telegram import Bot
from ..db import tasks as tasks_db, users as users_db
from ..message_utils import send_chunked_lines
from ..time_utils import now_sgt, relative_day_label

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
    if row["type"] == "interview":
        deadline_str = relative_day_label(row["interview_date"], is_deadline=False)
    elif row["deadline"]:
        deadline_str = relative_day_label(row["deadline"], is_deadline=True)
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
        assessments = [row for row in tasks if row["type"] in ("oa", "hirevue")]
        interviews = [row for row in tasks if row["type"] == "interview"]
        offers = tasks_db.get_applications_by_status(telegram_id, "offer")
        rejections = tasks_db.get_applications_by_status(telegram_id, "rejected")

        lines = [f"☀️ <b>Daily Digest</b> <code>{now_sgt().strftime('%d %b %Y')}</code>", ""]
        primary_sections = [
            ("📝 Applications Submitted", applications, _format_application),
            ("💻 Pending Assessments", assessments, _format_task),
            ("📞 Interviews", interviews, _format_task),
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
            await send_chunked_lines(
                bot,
                telegram_id,
                lines,
                parse_mode="HTML",
            )
        except Exception:
            pass
