from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from ..db import users, tasks as tasks_db
from ..gmail.fetch import fetch_new_messages
from ..gmail.parse import extract_subject_and_body, get_gmail_id
from ..llm.classify import classify_email


async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    user = users.get_user(telegram_id)

    if not user:
        await update.message.reply_text("Please run /start first.")
        return

    if not user["gmail_token_json"]:
        await update.message.reply_text("Gmail not connected. Use /connect first.")
        return

    await update.message.reply_text("Scanning your inbox...")

    last_scanned = None
    if user["last_scanned_at"]:
        try:
            last_scanned = datetime.fromisoformat(user["last_scanned_at"])
        except ValueError:
            pass

    messages = fetch_new_messages(user["gmail_token_json"], last_scanned)
    cycle_id = user["active_cycle_id"]
    found = []
    low_confidence = []

    for msg in messages:
        gmail_id = get_gmail_id(msg)
        subject, body = extract_subject_and_body(msg)

        try:
            result = classify_email(subject, body)
        except Exception:
            continue

        if result.get("type") == "irrelevant":
            continue

        confidence = result.get("confidence", 1.0)
        task_type = result.get("type", "application")
        company = result.get("company") or "Unknown"
        role = result.get("role") or ""
        deadline = result.get("deadline")
        link = result.get("link")

        source_application_id = None
        if task_type in ("oa", "hirevue", "interview") and cycle_id:
            source_application_id = tasks_db.find_or_create_application(
                telegram_id, cycle_id, company, role
            )

        task_id = tasks_db.insert_task(
            telegram_id, cycle_id, gmail_id, task_type,
            company, role, deadline, link, source_application_id,
        )

        if task_id is None:
            continue

        if confidence < 0.7:
            low_confidence.append((company, task_type, confidence))
        else:
            found.append((company, task_type))

    users.update_last_scanned(telegram_id)

    if not found and not low_confidence:
        await update.message.reply_text("Scan complete. No new tasks found.")
        return

    lines = [f"Scan complete. Found {len(found) + len(low_confidence)} new item(s):\n"]
    for company, task_type in found:
        lines.append(f"• {company} — {task_type.upper()}")
    for company, task_type, conf in low_confidence:
        lines.append(f"• {company} — {task_type.upper()} ⚠️ low confidence ({conf:.0%}) — please verify")

    await update.message.reply_text("\n".join(lines))
