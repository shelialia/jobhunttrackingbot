import asyncio
from datetime import datetime
from telegram import Bot, Update
from telegram.ext import ContextTypes
from ..db import users, tasks as tasks_db
from ..gmail.fetch import fetch_new_messages
from ..gmail.parse import extract_subject_and_body, get_gmail_id, get_email_date
from ..llm.classify import classify_email

_EMOJI = {"oa": "💻", "hirevue": "🎥", "interview": "📞", "application": "📝"}


async def _run_scan(bot: Bot, telegram_id: int, user: dict) -> None:
    # TEMP: hardcoded for testing — remove before deploy
    last_scanned = datetime(2026, 4, 20)

    messages = fetch_new_messages(user["gmail_token_json"], last_scanned)
    found = []
    low_confidence = []

    for msg in messages:
        gmail_id = get_gmail_id(msg)
        email_date = get_email_date(msg)
        subject, body = extract_subject_and_body(msg)

        try:
            result = classify_email(subject, body, email_date=email_date)
            await asyncio.sleep(20)
        except Exception as e:
            print(f"CLASSIFY ERROR for '{subject}': {e}")
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
        if task_type in ("oa", "hirevue", "interview"):
            source_application_id = tasks_db.find_application_for_linking(telegram_id, company, role)

        task_id = tasks_db.insert_task(
            telegram_id, gmail_id, task_type,
            company, role, deadline, link, source_application_id,
            email_date=email_date,
        )

        if task_id is None:
            continue

        if confidence < 0.7:
            low_confidence.append((company, task_type, confidence))
        else:
            found.append((company, task_type))

    users.update_last_scanned(telegram_id)

    if not found and not low_confidence:
        text = "✅ Scan complete — no new tasks found."
    else:
        lines = [f"✅ *Scan complete!* Found *{len(found) + len(low_confidence)}* new item(s):\n"]
        for company, task_type in found:
            emoji = _EMOJI.get(task_type, "📌")
            lines.append(f"{emoji} *{company}* — {task_type.upper()}")
        for company, task_type, conf in low_confidence:
            emoji = _EMOJI.get(task_type, "📌")
            lines.append(f"{emoji} *{company}* — {task_type.upper()} ⚠️ _low confidence ({conf:.0%}) — please verify_")
        text = "\n".join(lines)

    await bot.send_message(chat_id=telegram_id, text=text, parse_mode="Markdown")


async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    user = users.get_user(telegram_id)

    if not user:
        await update.message.reply_text("Please run /start first.")
        return

    if not user["gmail_token_json"]:
        await update.message.reply_text("Gmail not connected. Use /connect first.")
        return

    await update.message.reply_text(
        "⏳ *Scanning your inbox...*\n\nThis may take a few minutes — I'll send you a notification when done!",
        parse_mode="Markdown",
    )
    asyncio.create_task(_run_scan(context.bot, telegram_id, dict(user)))
