import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_TIMEZONE = os.getenv("BOT_TIMEZONE", "Asia/Singapore")


def _timezone(tz_name: str | None = None) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name or DEFAULT_TIMEZONE)
    except ZoneInfoNotFoundError:
        return ZoneInfo("Asia/Singapore")


def now_local(tz_name: str | None = None) -> datetime:
    return datetime.now(_timezone(tz_name))


def to_local(value, tz_name: str | None = None) -> datetime | None:
    dt = parse_datetime(value)
    if dt is None:
        return None
    return dt.astimezone(_timezone(tz_name))


def parse_datetime(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def now_sgt() -> datetime:
    return now_local("Asia/Singapore")


def to_sgt(value) -> datetime | None:
    return to_local(value, "Asia/Singapore")


def relative_day_label(value, *, is_deadline: bool, tz_name: str | None = None) -> str:
    target = to_local(value, tz_name)
    if target is None:
        return "no deadline" if is_deadline else "UNSCHEDULED"

    days = (target.date() - now_local(tz_name).date()).days
    if days < 0:
        return f"⚠️ OVERDUE {abs(days)}d ago"
    if days == 0:
        return "🔴 DUE TODAY" if is_deadline else "🔴 TODAY"
    return f"{days}d remaining"
