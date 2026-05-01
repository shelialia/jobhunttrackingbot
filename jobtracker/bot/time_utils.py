from datetime import datetime, timedelta, timezone


SGT = timezone(timedelta(hours=8))


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
    return datetime.now(SGT)


def to_sgt(value) -> datetime | None:
    dt = parse_datetime(value)
    if dt is None:
        return None
    return dt.astimezone(SGT)


def relative_day_label(value, *, is_deadline: bool) -> str:
    target = to_sgt(value)
    if target is None:
        return "no deadline" if is_deadline else "UNSCHEDULED"

    days = (target.date() - now_sgt().date()).days
    if days < 0:
        return f"⚠️ OVERDUE {abs(days)}d ago"
    if days == 0:
        return "🔴 DUE TODAY" if is_deadline else "🔴 TODAY"
    return f"{days}d remaining"
