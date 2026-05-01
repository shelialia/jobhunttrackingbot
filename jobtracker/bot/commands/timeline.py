from datetime import datetime
from html import escape

from telegram import Update
from telegram.ext import ContextTypes

from ..db import cycles as cycles_db, tasks as tasks_db, users


def _row_datetime(row) -> datetime:
    raw = row["email_date"] or row["created_at"]
    if isinstance(raw, datetime):
        return raw
    return datetime.fromisoformat(raw)


def _format_date(row) -> str:
    return _row_datetime(row).strftime("%d %b").lstrip("0")


def _format_interview_stage(row) -> tuple[str, str]:
    round_number = row["interview_round"] or 1
    if row["is_final_round"]:
        return "🏁", f"Round {round_number}: Final Round"
    if round_number == 1:
        label = row["round_label"] or "Phone Screen"
        return "📞", f"Round 1: {label.title()}"
    label = row["round_label"] or f"Round {round_number}"
    if row["round_label"]:
        return "💻", f"Round {round_number}: {label.title()}"
    return "💻", label


async def timeline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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

    if not context.args:
        await update.message.reply_text("Use /timeline <app_number>.")
        return

    try:
        app_index = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Use /timeline <app_number>.")
        return

    rows = tasks_db.get_cycle_applications(telegram_id, cycle["id"])
    if app_index < 1 or app_index > len(rows):
        await update.message.reply_text("That application number is out of range for the active cycle.")
        return

    root = rows[app_index - 1]
    chain_rows = tasks_db.get_chain_rows(root["id"])
    chain_rows.sort(key=_row_datetime)

    company = escape(root["company"] or "Unknown")
    role = escape(root["role"] or "")
    title = f"🏢 <b>{company}</b>"
    if role:
        title += f" - <i>{role}</i>"

    lines = ["──────────────────────────────────────────"]
    for row in chain_rows:
        if row["type"] == "application":
            emoji, label = "✅", "Applied"
        elif row["type"] == "oa":
            emoji, label = "📝", "OA"
        elif row["type"] == "hirevue":
            emoji, label = "🎥", "HireVue"
        elif row["type"] == "interview":
            emoji, label = _format_interview_stage(row)
        elif row["type"] == "offer":
            emoji, label = "🎉", "Offer"
        elif row["type"] == "rejection":
            emoji, label = "❌", "Rejection"
        else:
            continue

        if row["is_ghost"] and row["type"] == "interview":
            label += " (Inferred)"

        lines.append(f"{emoji} {label:<28} {_format_date(row)}")

    await update.message.reply_text(
        title + "\n<pre>" + escape("\n".join(lines)) + "</pre>",
        parse_mode="HTML",
    )
