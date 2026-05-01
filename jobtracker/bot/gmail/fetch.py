import logging
from datetime import datetime
from typing import Optional
from googleapiclient.discovery import build
from .auth import get_credentials

logger = logging.getLogger(__name__)


def fetch_new_messages(token_json: str, last_scanned_at: Optional[datetime]) -> list[dict]:
    creds = get_credentials(token_json)
    service = build("gmail", "v1", credentials=creds)

    query = (
        'subject:('
        'application OR applying OR update OR interview OR offer OR unfortunately OR regret '
        'OR "move forward" OR assessment OR challenge OR test OR codesignal OR hackerrank '
        'OR codility OR hirevue OR "technical screen" OR "online assessment" OR oa'
        ')'
    )
    if last_scanned_at:
        query += f" after:{int(last_scanned_at.timestamp())}"

    logger.info("Gmail fetch query: %s", query)
    results = service.users().messages().list(userId="me", q=query, maxResults=50).execute()
    messages = results.get("messages", [])
    logger.info("Gmail fetch returned %s message(s)", len(messages))

    full_messages = []
    for msg in messages:
        full = service.users().messages().get(userId="me", id=msg["id"], format="full").execute()
        full_messages.append(full)

    return full_messages
