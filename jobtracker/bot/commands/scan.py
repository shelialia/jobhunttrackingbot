import asyncio
import logging
from html import escape
from datetime import datetime, timedelta, timezone
from google.api_core import exceptions as google_exceptions
from telegram import Bot, Update
from telegram.ext import ContextTypes
from ..db import users, tasks as tasks_db, cycles as cycles_db
from ..gmail.fetch import fetch_new_messages
from ..gmail.parse import extract_subject_and_body, get_gmail_id, get_email_date
from ..llm.classify import classify_email

logger = logging.getLogger(__name__)
_CLASSIFY_RETRY_DELAYS = (2, 5, 10)
_SGT = timezone(timedelta(hours=8))

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


def _to_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _format_scan_datetime(dt: datetime) -> str:
    return dt.astimezone(_SGT).strftime("%d %b %I:%M %p").lstrip("0")


def _calculate_scan_start(user: dict, now_utc: datetime) -> tuple[datetime, bool]:
    last_scan = _to_utc(user.get("last_scanned_at"))
    capped_start = now_utc - timedelta(hours=24)
    if last_scan is None:
        return capped_start, False
    if last_scan >= capped_start:
        last_manual = _to_utc(user.get("last_manual_scanned_at"))
        return last_scan, last_manual is not None and last_manual == last_scan
    return capped_start, False


async def _classify_with_retry(subject: str, body: str, email_date: str | None = None) -> dict:
    attempts = len(_CLASSIFY_RETRY_DELAYS) + 1

    for attempt in range(1, attempts + 1):
        try:
            return classify_email(subject, body, email_date=email_date)
        except (
            google_exceptions.InternalServerError,
            google_exceptions.ServiceUnavailable,
            google_exceptions.DeadlineExceeded,
            google_exceptions.TooManyRequests,
        ) as exc:
            if attempt == attempts:
                raise

            delay = _CLASSIFY_RETRY_DELAYS[attempt - 1]
            logger.warning(
                "Retrying classify for %r after %s (%s/%s, sleep=%ss)",
                subject,
                type(exc).__name__,
                attempt,
                attempts,
                delay,
            )
            await asyncio.sleep(delay)


async def _run_scan(
    bot: Bot,
    telegram_id: int,
    user: dict,
    *,
    scan_start: datetime,
    scan_started_at: datetime,
    scan_mode: str,
    window_from_last_manual_scan: bool,
) -> None:
    cycle = cycles_db.get_active_cycle(telegram_id)
    if not cycle:
        await bot.send_message(
            chat_id=telegram_id,
            text="⚠️ No active cycle. Use /newcycle to create one before scanning.",
        )
        return
    cycle_id = cycle["id"]
    formatted_since = _format_scan_datetime(scan_start)

    await bot.send_message(
        chat_id=telegram_id,
        text=f"🔍 Scanning emails since {formatted_since}...",
    )

    messages = fetch_new_messages(user["gmail_token_json"], scan_start)
    messages.sort(key=_message_sort_key)
    # each entry: (company, task_type, role, email_date, low_conf)
    items: list[tuple[str, str, str, str | None, bool]] = []

    for msg in messages:
        gmail_id = get_gmail_id(msg)
        email_date = get_email_date(msg)
        subject, body = extract_subject_and_body(msg)

        try:
            result = await _classify_with_retry(subject, body, email_date=email_date)
            await asyncio.sleep(5)
        except Exception as e:
            logger.exception(
                "CLASSIFY ERROR for %r (%s): %s",
                subject,
                type(e).__name__,
                e,
            )
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
            existing_application_id = tasks_db.find_existing_application(
                telegram_id,
                company,
                role,
                cycle_id=cycle_id,
            )
            if existing_application_id is not None:
                existing_application = tasks_db.get_task_by_id(existing_application_id)
                if existing_application is None:
                    continue
                if existing_application["gmail_id"] == gmail_id:
                    continue

                tasks_db.merge_application_email(
                    existing_application_id,
                    gmail_id,
                    company,
                    role,
                    deadline=deadline,
                    link=link,
                    email_date=email_date,
                )
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

    users.update_last_scanned(
        telegram_id,
        scan_started_at,
        is_manual=(scan_mode == "manual"),
    )

    applications = [i for i in items if i[1] == "application"]
    tasks = [i for i in items if i[1] in ("oa", "hirevue", "interview")]
    rejections = [i for i in items if i[1] == "rejection"]
    offers = [i for i in items if i[1] == "offer"]

    since_text = escape(_format_scan_datetime(scan_start))
    if scan_mode == "manual":
        header = f"✅ Scan complete! (since {since_text})"
    else:
        suffix = " — last manual scan" if window_from_last_manual_scan else ""
        header = f"🤖 Daily auto-scan complete! (since {since_text}{escape(suffix)})"

    lines = [header, ""]
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


async def run_daily_auto_scan(bot: Bot) -> None:
    now_utc = datetime.now(timezone.utc)

    for user in users.get_all_users():
        if not user["gmail_token_json"]:
            continue

        telegram_id = user["telegram_id"]
        user_dict = dict(user)
        scan_start, from_last_manual_scan = _calculate_scan_start(user_dict, now_utc)
        await _run_scan(
            bot,
            telegram_id,
            user_dict,
            scan_start=scan_start,
            scan_started_at=now_utc,
            scan_mode="auto",
            window_from_last_manual_scan=from_last_manual_scan,
        )


async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    user = users.get_user(telegram_id)

    if not user:
        await update.message.reply_text("Please run /start first.")
        return

    if not user["gmail_token_json"]:
        await update.message.reply_text("Gmail not connected. Use /connect first.")
        return

    now_utc = datetime.now(timezone.utc)
    scan_start, from_last_manual_scan = _calculate_scan_start(dict(user), now_utc)
    asyncio.create_task(
        _run_scan(
            context.bot,
            telegram_id,
            dict(user),
            scan_start=scan_start,
            scan_started_at=now_utc,
            scan_mode="manual",
            window_from_last_manual_scan=from_last_manual_scan,
        )
    )
