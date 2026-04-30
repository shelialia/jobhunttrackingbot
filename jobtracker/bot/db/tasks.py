import sqlite3
from datetime import datetime, timedelta
from typing import Optional
from .schema import get_connection


def _normalise(text: str) -> str:
    import re
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    for suffix in ["inc", "ltd", "llc", "corp", "limited", "co"]:
        text = re.sub(rf"\b{suffix}\b", "", text).strip()
    return text


def find_or_create_application(telegram_id: int, cycle_id: int, company: str, role: str) -> int:
    company_n = _normalise(company)
    role_n = _normalise(role)
    cutoff = (datetime.utcnow() - timedelta(days=90)).isoformat()

    with get_connection() as conn:
        row = conn.execute(
            """SELECT id FROM tasks
               WHERE telegram_id = ? AND cycle_id = ? AND type = 'application'
               AND company_normalised = ? AND role_normalised = ?
               AND created_at >= ?
               ORDER BY created_at ASC LIMIT 1""",
            (telegram_id, cycle_id, company_n, role_n, cutoff),
        ).fetchone()

        if row:
            return row["id"]

        cursor = conn.execute(
            """INSERT INTO tasks
               (telegram_id, cycle_id, type, company, company_normalised, role, role_normalised, status, is_ghost)
               VALUES (?, ?, 'application', ?, ?, ?, ?, 'incomplete', 1)""",
            (telegram_id, cycle_id, company, company_n, role, role_n),
        )
        return cursor.lastrowid


def insert_task(
    telegram_id: int,
    cycle_id: int,
    gmail_id: Optional[str],
    task_type: str,
    company: str,
    role: str,
    deadline: Optional[str],
    link: Optional[str],
    source_application_id: Optional[int] = None,
    is_ghost: int = 0,
) -> Optional[int]:
    company_n = _normalise(company)
    role_n = _normalise(role)

    with get_connection() as conn:
        try:
            cursor = conn.execute(
                """INSERT INTO tasks
                   (telegram_id, cycle_id, source_application_id, gmail_id, type,
                    company, company_normalised, role, role_normalised,
                    deadline, link, status, is_ghost)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'incomplete', ?)""",
                (telegram_id, cycle_id, source_application_id, gmail_id,
                 task_type, company, company_n, role, role_n,
                 deadline, link, is_ghost),
            )
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None


def get_incomplete_tasks(telegram_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """SELECT * FROM tasks
               WHERE telegram_id = ? AND status = 'incomplete' AND is_ghost = 0
               ORDER BY
                 CASE WHEN deadline IS NULL THEN 1 ELSE 0 END,
                 deadline ASC,
                 CASE type
                   WHEN 'interview' THEN 0
                   WHEN 'hirevue'   THEN 1
                   WHEN 'oa'        THEN 2
                   ELSE 3
                 END ASC""",
            (telegram_id,),
        ).fetchall()


def get_upcoming_tasks(telegram_id: int) -> list[sqlite3.Row]:
    cutoff = (datetime.utcnow() + timedelta(days=7)).isoformat()
    with get_connection() as conn:
        return conn.execute(
            """SELECT * FROM tasks
               WHERE telegram_id = ? AND status = 'incomplete' AND is_ghost = 0
               AND deadline IS NOT NULL AND deadline <= ?
               ORDER BY deadline ASC""",
            (telegram_id, cutoff),
        ).fetchall()


def get_tasks_due_soon(telegram_id: int) -> list[sqlite3.Row]:
    now = datetime.utcnow().isoformat()
    cutoff = (datetime.utcnow() + timedelta(hours=24)).isoformat()
    with get_connection() as conn:
        return conn.execute(
            """SELECT * FROM tasks
               WHERE telegram_id = ? AND status = 'incomplete'
               AND deadline BETWEEN ? AND ?
               AND nudged_at IS NULL""",
            (telegram_id, now, cutoff),
        ).fetchall()


def get_all_incomplete_tasks_for_all_users() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """SELECT * FROM tasks
               WHERE status = 'incomplete' AND is_ghost = 0
               ORDER BY telegram_id, deadline ASC NULLS LAST""",
        ).fetchall()


def get_all_tasks_due_soon() -> list[sqlite3.Row]:
    now = datetime.utcnow().isoformat()
    cutoff = (datetime.utcnow() + timedelta(hours=24)).isoformat()
    with get_connection() as conn:
        return conn.execute(
            """SELECT * FROM tasks
               WHERE status = 'incomplete'
               AND deadline BETWEEN ? AND ?
               AND nudged_at IS NULL""",
            (now, cutoff),
        ).fetchall()


def mark_done(task_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE tasks SET status = 'done', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (task_id,),
        )


def mark_nudged(task_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE tasks SET nudged_at = CURRENT_TIMESTAMP WHERE id = ?",
            (task_id,),
        )


def find_task_by_company(telegram_id: int, company: str) -> Optional[sqlite3.Row]:
    company_n = _normalise(company)
    with get_connection() as conn:
        return conn.execute(
            """SELECT * FROM tasks
               WHERE telegram_id = ? AND company_normalised = ?
               AND status = 'incomplete' AND is_ghost = 0
               ORDER BY created_at DESC LIMIT 1""",
            (telegram_id, company_n),
        ).fetchone()


def delete_task(task_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))


def insert_manual_task(
    telegram_id: int,
    cycle_id: int,
    company: str,
    role: str,
    task_type: str,
    deadline: Optional[str],
) -> int:
    company_n = _normalise(company)
    role_n = _normalise(role)
    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO tasks
               (telegram_id, cycle_id, type, company, company_normalised, role, role_normalised, deadline, status, is_ghost)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'incomplete', 0)""",
            (telegram_id, cycle_id, task_type, company, company_n, role, role_n, deadline),
        )
        return cursor.lastrowid
