import asyncio
from html import escape
from datetime import datetime
from telegram import Bot, Update
from telegram.ext import ContextTypes
from ..db import users, tasks as tasks_db, cycles as cycles_db
from ..gmail.fetch import fetch_new_messages
from ..gmail.parse import extract_subject_and_body, get_gmail_id, get_email_date
from ..llm.classify import classify_email

def _format_date(email_date: str | None) -> str:
    if not email_date:
        return ""
    try:
        dt = datetime.strptime(email_date, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%d %b").lstrip("0")
    except Exception:
        return ""


def _format_scan_item(company: str, role: str, email_date: str | None, low_conf: bool) -> str:
    date_str = _format_date(email_date)
    company_html = escape(company)
    role_html = escape(role)

    parts = [f"• <b>{company_html}</b>"]
    if role_html:
        parts.append(f" <i>{role_html}</i>")
    if date_str:
        parts.append(f" <code>{escape(date_str)}</code>")
    if low_conf:
        parts.append(" <i>Low confidence</i>")
    return "".join(parts)


def _message_sort_key(message: dict) -> tuple[int, str]:
    email_date = get_email_date(message)
    if not email_date:
        return (1, "")
    return (0, email_date)


async def _run_scan(bot: Bot, telegram_id: int, user: dict) -> None:
    cycle = cycles_db.get_active_cycle(telegram_id)
    if not cycle:
        await bot.send_message(
            chat_id=telegram_id,
            text="⚠️ No active cycle. Use /newcycle to create one before scanning.",
        )
        return
    cycle_id = cycle["id"]

    # TEMP: hardcoded for testing — remove before deploy
    last_scanned = datetime(2026, 4, 20)

    messages = fetch_new_messages(user["gmail_token_json"], last_scanned)
    messages.sort(key=_message_sort_key)
    # each entry: (company, task_type, role, email_date, low_conf)
    items: list[tuple[str, str, str, str | None, bool]] = []

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
        if task_type == "application":
            existing_application_id = tasks_db.find_or_create_application_for_linking(
                telegram_id,
                company,
                role,
                cycle_id=cycle_id,
                email_date=email_date,
                is_ghost_if_missing=0,
            )
            if existing_application_id is None:
                continue

            existing_application = tasks_db.get_task_by_id(existing_application_id)
            if existing_application and existing_application["gmail_id"] != gmail_id:
                if existing_application["email_date"] is None or existing_application["is_ghost"]:
                    tasks_db.merge_application_email(
                        existing_application_id,
                        gmail_id,
                        company,
                        role,
                        email_date=email_date,
                    )
                    items.append((company, task_type, role, email_date, confidence < 0.7))
                    continue

                task_id = tasks_db.insert_task(
                    telegram_id, gmail_id, task_type,
                    company, role, deadline, link, None,
                    email_date=email_date, cycle_id=cycle_id,
                )
                if task_id is None:
                    continue
                items.append((company, task_type, role, email_date, confidence < 0.7))
                continue

        if task_type in ("oa", "hirevue", "interview"):
            source_application_id = tasks_db.find_or_create_application_for_linking(
                telegram_id, company, role, cycle_id=cycle_id, email_date=email_date
            )
        elif task_type in ("offer", "rejection"):
            source_application_id = tasks_db.find_or_create_application_for_linking(
                telegram_id,
                company,
                role,
                cycle_id=cycle_id,
                email_date=email_date,
                is_ghost_if_missing=0,
            )
            if source_application_id is None:
                continue

            task_id = tasks_db.insert_task(
                telegram_id,
                gmail_id,
                task_type,
                company,
                role,
                deadline,
                link,
                source_application_id,
                email_date=email_date,
                cycle_id=cycle_id,
                status="done",
            )
            if task_id is None:
                continue

            tasks_db.promote_ghost_application(source_application_id)
            tasks_db.mark_status(
                source_application_id,
                "offer" if task_type == "offer" else "rejected",
            )
            items.append((company, task_type, role, email_date, confidence < 0.7))
            continue

        task_id = tasks_db.insert_task(
            telegram_id, gmail_id, task_type,
            company, role, deadline, link, source_application_id,
            email_date=email_date, cycle_id=cycle_id,
        )

        if task_id is None:
            continue

        items.append((company, task_type, role, email_date, confidence < 0.7))

    users.update_last_scanned(telegram_id)

    applications = [i for i in items if i[1] == "application"]
    tasks = [i for i in items if i[1] in ("oa", "hirevue", "interview")]
    rejections = [i for i in items if i[1] == "rejection"]
    offers = [i for i in items if i[1] == "offer"]

    lines = ["✅ <b>Scan complete!</b>", ""]
    for group_label, group in (
        ("📝 Applications Submitted", applications),
        ("🎯 Pending Tasks", tasks),
    ):
        lines.append(f"<u><b>{escape(group_label)}</b></u> <b>({len(group)})</b>")
        for company, _, role, email_date, low_conf in group:
            lines.append(_format_scan_item(company, role, email_date, low_conf))
        lines.append("")

    for group_label, group in (
        ("🎉 Offers", offers),
        ("❌ Rejections", rejections),
    ):
        if not group:
            continue
        lines.append(f"<u><b>{escape(group_label)}</b></u> <b>({len(group)})</b>")
        for company, _, role, email_date, low_conf in group:
            lines.append(_format_scan_item(company, role, email_date, low_conf))
        lines.append("")

    text = "\n".join(lines).strip()
    parse_mode = "HTML"

    await bot.send_message(chat_id=telegram_id, text=text, parse_mode=parse_mode)


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
