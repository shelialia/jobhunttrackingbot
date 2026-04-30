import base64
from datetime import datetime, timezone
from typing import Optional


def _decode_part(data: str) -> str:
    return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")


def _extract_body(payload: dict) -> str:
    mime = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data", "")

    if mime in ("text/plain", "text/html") and body_data:
        return _decode_part(body_data)

    for part in payload.get("parts", []):
        result = _extract_body(part)
        if result:
            return result

    return ""


def extract_subject_and_body(message: dict) -> tuple[str, str]:
    headers = message.get("payload", {}).get("headers", [])
    subject = next((h["value"] for h in headers if h["name"].lower() == "subject"), "")
    body = _extract_body(message.get("payload", {}))
    # Truncate body to keep Gemini prompt size reasonable
    return subject, body[:4000]


def get_gmail_id(message: dict) -> Optional[str]:
    return message.get("id")


def get_email_date(message: dict) -> Optional[str]:
    """Return the email's received date as an ISO 8601 string, or None."""
    ms = message.get("internalDate")
    if not ms:
        return None
    dt = datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S")
