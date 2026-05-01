from datetime import datetime, timedelta, timezone
from html import escape
from telegram import Bot
from ..db import cycles as cycles_db, tasks as tasks_db, users as users_db
from ..message_utils import send_chunked_lines
from ..time_utils import now_sgt, relative_day_label, to_sgt

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


def _format_action_context(row) -> str:
    context = []
    if row["type"] == "interview" and row["interview_round"] and row["round_label"]:
        context.append(f"round {row['interview_round']}")
    if row["role"]:
        context.append(row["role"])
    if not context:
        return ""
    return f" ({escape(', '.join(str(item) for item in context))})"


def _action_datetime(row) -> datetime | None:
    raw = row["interview_date"] if row["type"] == "interview" else row["deadline"]
    try:
        return to_sgt(raw)
    except (TypeError, ValueError):
        return None


def _format_action_item(row) -> str:
    company = escape(row["company"] or "Unknown")
    action_type = escape(_format_action_type(row))
    return f"- {company} — {action_type}{_format_action_context(row)}"


def _format_due_date(dt: datetime) -> str:
    return dt.strftime("%d %b").lstrip("0")


def _build_action_needed_lines(rows) -> list[str]:
    buckets = {"unscheduled": [], "overdue": [], "soon": []}
    current = now_sgt()

    for row in rows:
        due_at = _action_datetime(row)
        if due_at is None:
            buckets["unscheduled"].append(row)
        elif due_at < current:
            buckets["overdue"].append((row, due_at))
        else:
            buckets["soon"].append((row, due_at))

    if not any(buckets.values()):
        return []

    lines = ["⏰ <b>Action needed:</b>", ""]

    if buckets["unscheduled"]:
        lines.append(f"🔴 <b>UNSCHEDULED ({len(buckets['unscheduled'])})</b>")
        lines.extend(_format_action_item(row) for row in buckets["unscheduled"])
        lines.append("")

    if buckets["overdue"]:
        lines.append(f"🟠 <b>OVERDUE ({len(buckets['overdue'])})</b>")
        for row, due_at in buckets["overdue"]:
            company = escape(row["company"] or "Unknown")
            action_type = escape(_format_action_type(row))
            lines.append(f"- {company} — {action_type} was due {_format_due_date(due_at)}")
        lines.append("")

    if buckets["soon"]:
        lines.append(f"🟡 <b>DUE SOON ({len(buckets['soon'])})</b>")
        for row, due_at in buckets["soon"]:
            company = escape(row["company"] or "Unknown")
            action_type = escape(_format_action_type(row))
            days = max((due_at.date() - current.date()).days, 0)
            lines.append(f"- {company} — {action_type} due in {days}d")
        lines.append("")

    return lines[:-1] if lines[-1] == "" else lines


def _build_digest_lines(rows) -> list[str]:
    applications = [row for row in rows if row["type"] == "application"]
    tasks = [row for row in rows if row["type"] in ("oa", "hirevue", "interview")]
    assessments = [row for row in tasks if row["type"] in ("oa", "hirevue")]
    interviews = [row for row in tasks if row["type"] == "interview"]
    offers = [row for row in rows if row["type"] == "offer"]
    rejections = [row for row in rows if row["type"] == "rejection"]

    lines = [f"☀️ <b>Daily Digest</b> <code>{now_sgt().strftime('%d %b %Y')}</code>", ""]
    primary_sections = [
        ("📝 Applications Submitted", applications, _format_application),
        ("💻 Pending Assessments", assessments, _format_task),
        ("📞 Interviews", interviews, _format_task),
    ]

    for title, section_rows, formatter in primary_sections:
        lines.append(f"<u><b>{escape(title)}</b></u> <b>({len(section_rows)})</b>")
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

    lines.append("<i>Use /tasks for details or /done &lt;task_number&gt; to mark complete.</i>")
    return lines


async def send_daily_digest(bot: Bot) -> None:
    all_users = users_db.get_all_users()
    since = datetime.now(timezone.utc) - timedelta(hours=24)

    for user in all_users:
        if not user["gmail_token_json"]:
            continue

        telegram_id = user["telegram_id"]
        cycle = cycles_db.get_active_cycle(telegram_id)
        if not cycle:
            continue

        recent_rows = tasks_db.get_recent_classified_tasks(
            telegram_id,
            cycle["id"],
            since,
        )
        action_lines = _build_action_needed_lines(
            tasks_db.get_cycle_assessment_tasks(telegram_id, cycle["id"])
        )

        if recent_rows:
            try:
                await send_chunked_lines(
                    bot,
                    telegram_id,
                    _build_digest_lines(recent_rows),
                    parse_mode="HTML",
                )
            except Exception:
                pass

        if action_lines:
            try:
                await send_chunked_lines(
                    bot,
                    telegram_id,
                    action_lines,
                    parse_mode="HTML",
                )
            except Exception:
                pass
