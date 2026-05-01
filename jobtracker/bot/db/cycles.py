import sqlite3
from typing import Optional
from .schema import get_connection


def create_cycle(telegram_id: int, name: str) -> int:
    with get_connection() as conn:
        conn.execute(
            "UPDATE cycles SET is_active = 0, ended_at = CURRENT_TIMESTAMP WHERE telegram_id = ? AND is_active = 1",
            (telegram_id,),
        )
        cursor = conn.execute(
            "INSERT INTO cycles (telegram_id, name, is_active) VALUES (?, ?, 1)",
            (telegram_id, name),
        )
        return cursor.lastrowid


def get_active_cycle(telegram_id: int) -> Optional[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM cycles WHERE telegram_id = ? AND is_active = 1",
            (telegram_id,),
        ).fetchone()


def get_all_cycles(telegram_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM cycles WHERE telegram_id = ? ORDER BY started_at DESC",
            (telegram_id,),
        ).fetchall()


def end_cycle(cycle_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE cycles SET is_active = 0, ended_at = CURRENT_TIMESTAMP WHERE id = ?",
            (cycle_id,),
        )


def switch_to_cycle(telegram_id: int, cycle_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE cycles SET is_active = 0, ended_at = CURRENT_TIMESTAMP WHERE telegram_id = ? AND is_active = 1",
            (telegram_id,),
        )
        conn.execute(
            "UPDATE cycles SET is_active = 1, ended_at = NULL WHERE id = ?",
            (cycle_id,),
        )


def get_cycle_summary(telegram_id: int, cycle_id: int) -> dict:
    with get_connection() as conn:
        apps = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE telegram_id = ? AND cycle_id = ? AND type = 'application' AND is_ghost = 0",
            (telegram_id, cycle_id),
        ).fetchone()[0]
        interviews = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE telegram_id = ? AND cycle_id = ? AND type IN ('oa', 'hirevue', 'interview')",
            (telegram_id, cycle_id),
        ).fetchone()[0]
        offers = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE telegram_id = ? AND cycle_id = ? AND type = 'application' AND status = 'offer'",
            (telegram_id, cycle_id),
        ).fetchone()[0]
        return {"apps": apps, "interviews": interviews, "offers": offers}
