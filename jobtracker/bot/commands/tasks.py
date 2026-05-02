from datetime import datetime
from html import escape
from telegram import Update
from telegram.ext import ContextTypes
from ..db import tasks, users
from ..message_utils import reply_chunked_lines
from ..time_utils import now_local, to_local

_EMOJI = {"oa": "💻", "hirevue": "🎥", "interview": "📞"}


def _action_datetime(row, tz_name: str | None = None) -> datetime | None:
    raw = row["interview_date"] if row["type"] == "interview" else row["deadline"]
    try:
        return to_local(raw, tz_name)
    except (TypeError, ValueError):
        return None


def _format_type_label(row) -> str:
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


def _format_due_date(dt: datetime) -> str:
    return dt.strftime("%d %b").lstrip("0")


def _assessment_status(row, current, tz_name: str | None = None) -> str:
    due_at = _action_datetime(row, tz_name)
    if due_at is None:
        return "unscheduled"
    days = (due_at.date() - current.date()).days
    if days < 0:
        return f"⚠️ was due {_format_due_date(due_at)}"
    if days == 0:
        return "🔥 <b>TODAY</b>"
    return f"due in {days}d"


def _interview_status(row, current, tz_name: str | None = None) -> str:
    due_at = _action_datetime(row, tz_name)
    if due_at is None:
        return "unscheduled"
    days = (due_at.date() - current.date()).days
    if days < 0:
        return f"happened {abs(days)}d ago"
    if days == 0:
        return "🔥 <b>TODAY</b>"
    return f"happening in {days}d"


def _sort_key(row, current, tz_name: str | None = None) -> tuple:
    due_at = _action_datetime(row, tz_name)
    if due_at is None:
        return (0, "")
    if due_at < current:
        return (1, due_at.isoformat())
    return (2, due_at.isoformat())


def _format_item(n: int, row, status_html: str) -> str:
    company = escape(row["company"] or "Unknown")
    role = escape(row["role"]) if row["role"] else ""
    type_label = escape(_format_type_label(row))

    parts = [f"{n}. <b>{company}</b>"]
    if role:
        parts.append(f" <i>{role}</i>")
    parts.append(f" <code>{type_label}</code> — {status_html}")
    return "".join(parts)


async def tasks_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    user = users.get_user(telegram_id)
    tz_name = user["timezone"] if user and "timezone" in user.keys() else None
    rows = tasks.get_assessment_tasks(telegram_id)

    if not rows:
        await update.message.reply_text("🎉 No pending assessments or interviews right now!")
        return

    current = now_local(tz_name)
    assessments = sorted(
        [r for r in rows if r["type"] in ("oa", "hirevue")],
        key=lambda r: _sort_key(r, current, tz_name),
    )
    interviews = sorted(
        [r for r in rows if r["type"] == "interview"],
        key=lambda r: _sort_key(r, current, tz_name),
    )

    context.user_data["last_assessment_tasks"] = [r["id"] for r in assessments]
    context.user_data["last_interview_tasks"] = [r["id"] for r in interviews]
    context.user_data["last_remove_context"] = "tasks"

    lines = ["📋 <b>Pending Tasks</b>", ""]

    if assessments:
        lines.append(f"💻 <b>Upcoming Assessments ({len(assessments)})</b>")
        for i, row in enumerate(assessments, 1):
            lines.append(_format_item(i, row, _assessment_status(row, current, tz_name)))
        lines.append("")

    if interviews:
        lines.append(f"📞 <b>Upcoming Interviews ({len(interviews)})</b>")
        for i, row in enumerate(interviews, 1):
            lines.append(_format_item(i, row, _interview_status(row, current, tz_name)))
        lines.append("")

    lines.append("<i>/done &lt;assessment_index&gt; · /done i&lt;interview_index&gt;</i>")
    await reply_chunked_lines(update.message, lines, parse_mode="HTML")
