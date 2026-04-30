from datetime import datetime
from typing import Optional
from googleapiclient.discovery import build
from .auth import get_credentials


def fetch_new_messages(token_json: str, last_scanned_at: Optional[datetime]) -> list[dict]:
    creds = get_credentials(token_json)
    service = build("gmail", "v1", credentials=creds)

    query = "in:inbox category:primary"
    if last_scanned_at:
        query += f" after:{int(last_scanned_at.timestamp())}"

    results = service.users().messages().list(userId="me", q=query, maxResults=50).execute()
    messages = results.get("messages", [])

    full_messages = []
    for msg in messages:
        full = service.users().messages().get(userId="me", id=msg["id"], format="full").execute()
        full_messages.append(full)

    return full_messages
