import sqlite3
from typing import Optional
from .schema import get_connection


def create_cycle(telegram_id: int, label: str) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO cycles (telegram_id, label) VALUES (?, ?)",
            (telegram_id, label),
        )
        return cursor.lastrowid


def get_active_cycle(telegram_id: int) -> Optional[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM cycles WHERE telegram_id = ? AND status = 'active' ORDER BY started_at DESC LIMIT 1",
            (telegram_id,),
        ).fetchone()


def get_cycle_by_label(telegram_id: int, label: str) -> Optional[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM cycles WHERE telegram_id = ? AND label = ?",
            (telegram_id, label),
        ).fetchone()


def get_all_cycles(telegram_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM cycles WHERE telegram_id = ? ORDER BY started_at DESC",
            (telegram_id,),
        ).fetchall()


def close_cycle(cycle_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE cycles SET status = 'closed', ended_at = CURRENT_TIMESTAMP WHERE id = ?",
            (cycle_id,),
        )


def get_cycle_stats(cycle_id: int, telegram_id: int) -> dict:
    with get_connection() as conn:
        total_applied = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE cycle_id = ? AND telegram_id = ? AND type = 'application' AND is_ghost = 0",
            (cycle_id, telegram_id),
        ).fetchone()[0]

        responded = conn.execute(
            """SELECT COUNT(DISTINCT source_application_id) FROM tasks
               WHERE cycle_id = ? AND telegram_id = ? AND type != 'application'
               AND source_application_id IS NOT NULL""",
            (cycle_id, telegram_id),
        ).fetchone()[0]

        pending = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE cycle_id = ? AND telegram_id = ? AND status = 'incomplete' AND is_ghost = 0",
            (cycle_id, telegram_id),
        ).fetchone()[0]

        avg_response = conn.execute(
            """SELECT AVG(julianday(t.created_at) - julianday(a.created_at))
               FROM tasks t JOIN tasks a ON t.source_application_id = a.id
               WHERE t.cycle_id = ? AND t.telegram_id = ? AND t.type != 'application'""",
            (cycle_id, telegram_id),
        ).fetchone()[0]

        cycle = conn.execute("SELECT * FROM cycles WHERE id = ?", (cycle_id,)).fetchone()
        weeks = None
        if cycle and cycle["started_at"]:
            weeks_raw = conn.execute(
                "SELECT (julianday(CURRENT_TIMESTAMP) - julianday(?)) / 7.0",
                (cycle["started_at"],),
            ).fetchone()[0]
            weeks = max(weeks_raw, 1)

        completed_this_week = conn.execute(
            """SELECT COUNT(*) FROM tasks
               WHERE cycle_id = ? AND telegram_id = ? AND status = 'done'
               AND updated_at >= datetime('now', '-7 days')""",
            (cycle_id, telegram_id),
        ).fetchone()[0]

        return {
            "total_applied": total_applied,
            "responded": responded,
            "response_rate": round(responded / total_applied * 100, 1) if total_applied else 0,
            "pending": pending,
            "avg_response_days": round(avg_response, 1) if avg_response else None,
            "apps_per_week": round(total_applied / weeks, 1) if weeks else 0,
            "completed_this_week": completed_this_week,
        }
