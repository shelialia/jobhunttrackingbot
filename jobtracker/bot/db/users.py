import sqlite3
from datetime import datetime
from typing import Optional
from .schema import get_connection


def get_user(telegram_id: int) -> Optional[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()


def create_user(telegram_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (telegram_id) VALUES (?)", (telegram_id,)
        )


def update_email(telegram_id: int, email: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET email = ? WHERE telegram_id = ?", (email, telegram_id)
        )


def update_gmail_token(telegram_id: int, token_json: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET gmail_token_json = ? WHERE telegram_id = ?",
            (token_json, telegram_id),
        )


def update_last_scanned(telegram_id: int, scanned_at: datetime, is_manual: bool = False) -> None:
    scanned_at_text = scanned_at.strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        if is_manual:
            conn.execute(
                """UPDATE users
                   SET last_scanned_at = ?, last_manual_scanned_at = ?
                   WHERE telegram_id = ?""",
                (scanned_at_text, scanned_at_text, telegram_id),
            )
        else:
            conn.execute(
                "UPDATE users SET last_scanned_at = ? WHERE telegram_id = ?",
                (scanned_at_text, telegram_id),
            )



def get_all_users() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM users").fetchall()
