import logging
from datetime import datetime, timedelta, timezone
from html import escape
from telegram import Bot
from ..db import cycles as cycles_db, tasks as tasks_db, users as users_db
from ..message_utils import send_chunked_lines
from ..time_utils import now_local, relative_day_label, to_local

logger = logging.getLogger(__name__)

_TASK_EMOJI = {"oa": "💻", "hirevue": "🎥", "interview": "📞"}


def _format_application(row) -> str:
    company = escape(row["company"] or "Unknown")
    role = escape(row["role"]) if row["role"] else ""
    parts = [f"• <b>{company}</b>"]
    if role:
        parts.append(f" <i>{role}</i>")
    return "".join(parts)


def _format_task(row, tz_name: str | None = None) -> str:
    company = escape(row["company"] or "Unknown")
    emoji = _TASK_EMOJI.get(row["type"], "📌")
    type_label = escape(row["type"].upper())
    role = escape(row["role"]) if row["role"] else ""
    if row["type"] == "interview":
        deadline_str = relative_day_label(row["interview_date"], is_deadline=False, tz_name=tz_name)
    elif row["deadline"]:
        deadline_str = relative_day_label(row["deadline"], is_deadline=True, tz_name=tz_name)
    else:
        deadline_str = "no deadline"

    parts = [f"• {emoji} <b>{company}</b>"]
    if role:
        parts.append(f" <i>{role}</i>")
    parts.append(f" <code>{type_label}</code>")
    parts.append(f" <i>{escape(deadline_str)}</i>")
    return "".join(parts)


def _format_action_type(row) -> str:
    if row["type"] == "oa":
        return "OA"
    if row["type"] == "hirevue":
        return "HireVue"
    if row["type"] != "interview":
        return row["type"].upper()

    if row["is_final_round"]:
        return "Final Round"
    if row["round_label"]:
        return str(row["round_label"]).title()
    if row["interview_round"]:
        return f"Round {row['interview_round']}"
    return "Interview"


def _action_datetime(row, tz_name: str | None = None) -> datetime | None:
    raw = row["interview_date"] if row["type"] == "interview" else row["deadline"]
    try:
        return to_local(raw, tz_name)
    except (TypeError, ValueError):
        return None


def _format_due_date(dt: datetime) -> str:
    return dt.strftime("%d %b").lstrip("0")


def _format_action_item(row, deadline_html: str | None = None) -> str:
    company = escape(row["company"] or "Unknown")
    role = escape(row["role"]) if row["role"] else ""
    type_label = escape(_format_action_type(row))

    parts = [f"• <b>{company}</b>"]
    if role:
        parts.append(f" <i>{role}</i>")
    parts.append(f" <code>{type_label}</code>")
    if deadline_html:
        parts.append(f" — {deadline_html}")
    return "".join(parts)


def _assessment_date_html(row, current, tz_name: str | None = None) -> str:
    due_at = _action_datetime(row, tz_name)
    if due_at is None:
        return "unscheduled"
    days = (due_at.date() - current.date()).days
    if days < 0:
        return f"⚠️ was due {_format_due_date(due_at)}"
    if days == 0:
        return "🔥 <b>TODAY</b>"
    return f"due in {days}d"


def _interview_date_html(row, current, tz_name: str | None = None) -> str:
    due_at = _action_datetime(row, tz_name)
    if due_at is None:
        return "unscheduled"
    days = (due_at.date() - current.date()).days
    if days < 0:
        return f"happened {abs(days)}d ago"
    if days == 0:
        return "🔥 <b>TODAY</b>"
    return f"happening in {days}d"


def _sort_key_for_action(row, current, tz_name: str | None = None) -> tuple:
    due_at = _action_datetime(row, tz_name)
    if due_at is None:
        return (0, "")
    if due_at < current:
        return (1, due_at.isoformat())
    return (2, due_at.isoformat())


def _build_action_needed_lines(rows, tz_name: str | None = None) -> list[str]:
    assessments = []
    interviews = []
    current = now_local(tz_name)

    for row in rows:
        if row["type"] == "interview":
            interviews.append(row)
        else:
            assessments.append(row)

    if not assessments and not interviews:
        return []

    assessments.sort(key=lambda r: _sort_key_for_action(r, current, tz_name))
    interviews.sort(key=lambda r: _sort_key_for_action(r, current, tz_name))

    lines = ["⏰ <b>Action needed:</b>", ""]

    if assessments:
        lines.append(f"💻 <b>Assessments ({len(assessments)})</b>")
        for row in assessments:
            lines.append(_format_action_item(row, _assessment_date_html(row, current, tz_name)))
        lines.append("")

    if interviews:
        lines.append(f"📞 <b>Interviews ({len(interviews)})</b>")
        for row in interviews:
            lines.append(_format_action_item(row, _interview_date_html(row, current, tz_name)))
        lines.append("")

    return lines[:-1] if lines[-1] == "" else lines


async def send_action_needed(
    bot: Bot,
    telegram_id: int,
    cycle_id: int,
    tz_name: str | None = None,
) -> None:
    action_rows = tasks_db.get_cycle_assessment_tasks(telegram_id, cycle_id)
    action_lines = _build_action_needed_lines(action_rows, tz_name)
    if not action_lines:
        return
    try:
        await send_chunked_lines(bot, telegram_id, action_lines, parse_mode="HTML")
    except Exception:
        logger.exception("Failed to send action lines to %d", telegram_id)


def _build_digest_lines(rows, tz_name: str | None = None) -> list[str]:
    applications = [row for row in rows if row["type"] == "application"]
    tasks = [row for row in rows if row["type"] in ("oa", "hirevue", "interview")]
    assessments = [row for row in tasks if row["type"] in ("oa", "hirevue")]
    interviews = [row for row in tasks if row["type"] == "interview"]
    offers = [row for row in rows if row["type"] == "offer"]
    rejections = [row for row in rows if row["type"] == "rejection"]

    lines = [f"☀️ <b>Daily Digest</b> <code>{now_local(tz_name).strftime('%d %b %Y')}</code>", ""]
    primary_sections = [
        ("📝 Applications Submitted", applications, _format_application),
        ("💻 Pending Assessments", assessments, _format_task),
        ("📞 Interviews", interviews, _format_task),
    ]

    for title, section_rows, formatter in primary_sections:
        lines.append(f"<u><b>{escape(title)}</b></u> <b>({len(section_rows)})</b>")
        if formatter is _format_task:
            lines.extend(formatter(row, tz_name) for row in section_rows)
        else:
            lines.extend(formatter(row) for row in section_rows)
        lines.append("")

    for title, section_rows, formatter in (
        ("🎉 Offers", offers, _format_application),
        ("❌ Rejections", rejections, _format_application),
    ):
        if not section_rows:
            continue
        lines.append(f"<u><b>{escape(title)}</b></u> <b>({len(section_rows)})</b>")
        lines.extend(formatter(row) for row in section_rows)
        lines.append("")

    lines.append("<i>Use /tasks for details or /done &lt;assessment_index&gt; / /done i&lt;interview_index&gt; to mark complete.</i>")
    return lines


async def send_daily_digest(bot: Bot) -> None:
    all_users = users_db.get_all_users()
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    logger.info("Running daily digest for %d users", len(all_users))

    for user in all_users:
        if not user["gmail_token_json"]:
            continue

        telegram_id = user["telegram_id"]
        tz_name = user["timezone"] if "timezone" in user.keys() else None
        cycle = cycles_db.get_active_cycle(telegram_id)
        if not cycle:
            continue

        recent_rows = tasks_db.get_recent_classified_tasks(
            telegram_id,
            cycle["id"],
            since,
        )
        action_rows = tasks_db.get_cycle_assessment_tasks(telegram_id, cycle["id"])
        action_lines = _build_action_needed_lines(action_rows, tz_name)

        logger.info(
            "Digest for %d: %d recent rows, %d action rows",
            telegram_id, len(recent_rows), len(action_rows),
        )

        if recent_rows:
            try:
                await send_chunked_lines(
                    bot,
                    telegram_id,
                    _build_digest_lines(recent_rows, tz_name),
                    parse_mode="HTML",
                )
            except Exception:
                logger.exception("Failed to send digest body to %d", telegram_id)

        if action_lines:
            try:
                await send_chunked_lines(
                    bot,
                    telegram_id,
                    action_lines,
                    parse_mode="HTML",
                )
            except Exception:
                logger.exception("Failed to send action lines to %d", telegram_id)
