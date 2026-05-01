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
from ..message_utils import send_chunked_lines

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


def determine_interview_round(
    gemini_round: int | None,
    is_final_round: int,
    root_app_id: int,
) -> int:
    if gemini_round is not None:
        return gemini_round

    _ = is_final_round
    existing = tasks_db.count_interviews_in_chain(root_app_id)
    return existing + 1


def _calculate_scan_start(
    user: dict,
    cycle: dict,
    now_utc: datetime,
    scan_mode: str,
) -> tuple[datetime, bool, bool]:
    cycle_started_at = _to_utc(cycle.get("started_at"))
    last_manual_scan = _to_utc(user.get("last_manual_scanned_at"))
    first_manual_scan_for_cycle = (
        scan_mode == "manual"
        and cycle_started_at is not None
        and (last_manual_scan is None or last_manual_scan < cycle_started_at)
    )
    if first_manual_scan_for_cycle:
        return now_utc - timedelta(days=14), False, True

    last_scan = _to_utc(user.get("last_scanned_at"))
    capped_start = now_utc - timedelta(hours=24)
    if last_scan is None:
        return capped_start, False, False
    if last_scan >= capped_start:
        return last_scan, last_manual_scan is not None and last_manual_scan == last_scan, False
    return capped_start, False, False


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
    scan_started_at: datetime,
    scan_mode: str,
) -> None:
    cycle = cycles_db.get_active_cycle(telegram_id)
    if not cycle:
        await bot.send_message(
            chat_id=telegram_id,
            text="⚠️ No active cycle. Use /newcycle to create one before scanning.",
        )
        return
    cycle_id = cycle["id"]
    scan_start, window_from_last_manual_scan, first_manual_scan_for_cycle = _calculate_scan_start(
        user,
        dict(cycle),
        scan_started_at,
        scan_mode,
    )
    formatted_since = _format_scan_datetime(scan_start)

    await bot.send_message(
        chat_id=telegram_id,
        text=(
            f"🔍 <b>Scanning emails since {escape(formatted_since)}...</b>"
            + ("\n📥 <i>First sync for this cycle</i>" if first_manual_scan_for_cycle else "")
        ),
        parse_mode="HTML",
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
        raw_interview_round = result.get("interview_round")
        try:
            interview_round = int(raw_interview_round) if raw_interview_round not in (None, "") else None
        except (TypeError, ValueError):
            interview_round = None
        is_final_round = 1 if result.get("is_final_round") in (1, True, "1") else 0
        round_label = result.get("round_label")
        interview_date = result.get("interview_date")
        interview_platform = result.get("interview_platform")
        email_subtype = result.get("email_subtype") or "unknown"
        if task_type == "interview" and not interview_date:
            deadline = None

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

        if task_type == "interview":
            root_application_id = tasks_db.find_or_create_application_for_linking(
                telegram_id, company, role, cycle_id=cycle_id, email_date=email_date
            )
            if root_application_id is None:
                continue
            root_application_id = tasks_db.get_root_application_id(root_application_id) or root_application_id
            interview_round = determine_interview_round(
                interview_round,
                is_final_round,
                root_application_id,
            )
            existing_interview = tasks_db.find_existing_interview(
                telegram_id,
                cycle_id,
                company,
                interview_round=interview_round,
            )
            if existing_interview is not None:
                if existing_interview["gmail_id"] == gmail_id:
                    continue

                source_application_id = existing_interview["source_application_id"]
                if source_application_id is None:
                    source_application_id = tasks_db.ensure_interview_chain(
                        telegram_id,
                        cycle_id,
                        root_application_id,
                        company,
                        role,
                        interview_round,
                    )
                tasks_db.update_interview_task(
                    existing_interview["id"],
                    gmail_id=gmail_id,
                    source_application_id=source_application_id,
                    company=company,
                    role=role,
                    deadline=deadline,
                    link=link,
                    email_date=email_date,
                    interview_round=interview_round,
                    is_final_round=1 if is_final_round else None,
                    round_label=round_label,
                    interview_date=interview_date,
                    interview_platform=interview_platform,
                    confirmed_at=email_date if email_subtype == "confirmation" else None,
                )
                items.append((company, task_type, role, email_date, confidence < 0.7))
                continue

            source_application_id = tasks_db.ensure_interview_chain(
                telegram_id,
                cycle_id,
                root_application_id,
                company,
                role,
                interview_round,
            )
            if source_application_id is None:
                continue

        if task_type in ("oa", "hirevue"):
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
                is_ghost_if_missing=1,
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
            interview_round=interview_round if task_type == "interview" else None,
            is_final_round=is_final_round if task_type == "interview" else 0,
            round_label=round_label if task_type == "interview" else None,
            interview_date=interview_date if task_type == "interview" else None,
            interview_platform=interview_platform if task_type == "interview" else None,
            confirmed_at=(
                email_date
                if task_type == "interview" and email_subtype == "confirmation"
                else None
            ),
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
    assessments = [i for i in items if i[1] in ("oa", "hirevue")]
    interviews = [i for i in items if i[1] == "interview"]
    rejections = [i for i in items if i[1] == "rejection"]
    offers = [i for i in items if i[1] == "offer"]

    since_text = escape(_format_scan_datetime(scan_start))
    if scan_mode == "manual":
        header = f"✅ <b>Scan complete!</b> <code>(since {since_text})</code>"
        if first_manual_scan_for_cycle:
            header += "\n📬 <i>Cycle backfill complete</i>"
    else:
        suffix = " — last manual scan" if window_from_last_manual_scan else ""
        header = f"🤖 <b>Daily auto-scan complete!</b> <code>(since {since_text}{escape(suffix)})</code>"

    lines = [header, ""]
    for group_label, group in (
        ("📝 Applications Submitted", applications),
        ("💻 Pending Assessments", assessments),
        ("📞 Interviews", interviews),
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

    await send_chunked_lines(
        bot,
        telegram_id,
        "\n".join(lines).strip().split("\n"),
        parse_mode="HTML",
    )


async def run_daily_auto_scan(bot: Bot) -> None:
    now_utc = datetime.now(timezone.utc)

    for user in users.get_all_users():
        if not user["gmail_token_json"]:
            continue

        telegram_id = user["telegram_id"]
        user_dict = dict(user)
        await _run_scan(
            bot,
            telegram_id,
            user_dict,
            scan_started_at=now_utc,
            scan_mode="auto",
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

    asyncio.create_task(
        _run_scan(
            context.bot,
            telegram_id,
            dict(user),
            scan_started_at=datetime.now(timezone.utc),
            scan_mode="manual",
        )
    )
