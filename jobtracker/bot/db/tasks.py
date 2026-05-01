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


def _find_matching_application(
    telegram_id: int,
    company: str,
    role: str,
    cycle_id: Optional[int] = None,
    include_ghost: bool = False,
) -> Optional[int]:
    from rapidfuzz import fuzz

    company_n = _normalise(company)
    role_n = _normalise(role)
    cutoff = (datetime.utcnow() - timedelta(days=90)).isoformat()

    query = """SELECT id, role_normalised FROM tasks
               WHERE telegram_id = ? AND type = 'application'
               AND company_normalised = ? AND created_at >= ?"""
    params: list[object] = [telegram_id, company_n, cutoff]

    if cycle_id is not None:
        query += " AND cycle_id = ?"
        params.append(cycle_id)

    if not include_ghost:
        query += " AND is_ghost = 0"

    query += " ORDER BY created_at DESC"

    with get_connection() as conn:
        candidates = conn.execute(query, tuple(params)).fetchall()

    if not candidates:
        return None

    best_id, best_score = None, 0
    for row in candidates:
        score = fuzz.partial_ratio(role_n, row["role_normalised"] or "")
        if score > best_score:
            best_score, best_id = score, row["id"]

    return best_id if best_score >= 80 else None


def find_application_for_linking(telegram_id: int, company: str, role: str, cycle_id: Optional[int] = None) -> Optional[int]:
    """Return the most recent real application for this company with the best fuzzy role match, or None."""
    return _find_matching_application(
        telegram_id, company, role, cycle_id=cycle_id, include_ghost=False
    )


def find_or_create_application_for_linking(
    telegram_id: int,
    company: str,
    role: str,
    cycle_id: Optional[int] = None,
    email_date: Optional[str] = None,
    is_ghost_if_missing: int = 1,
) -> Optional[int]:
    app_id = find_application_for_linking(telegram_id, company, role, cycle_id=cycle_id)
    if app_id is not None:
        return app_id

    best_id = _find_matching_application(
        telegram_id, company, role, cycle_id=cycle_id, include_ghost=True
    )
    if best_id is not None:
        return best_id

    return insert_task(
        telegram_id=telegram_id,
        gmail_id=None,
        task_type="application",
        company=company,
        role=role,
        deadline=None,
        link=None,
        is_ghost=is_ghost_if_missing,
        email_date=email_date,
        cycle_id=cycle_id,
    )


def insert_task(
    telegram_id: int,
    gmail_id: Optional[str],
    task_type: str,
    company: str,
    role: str,
    deadline: Optional[str],
    link: Optional[str],
    source_application_id: Optional[int] = None,
    is_ghost: int = 0,
    email_date: Optional[str] = None,
    cycle_id: Optional[int] = None,
    status: str = "incomplete",
) -> Optional[int]:
    company_n = _normalise(company)
    role_n = _normalise(role)

    with get_connection() as conn:
        try:
            cursor = conn.execute(
                """INSERT INTO tasks
                   (telegram_id, cycle_id, source_application_id, gmail_id, type,
                    company, company_normalised, role, role_normalised,
                    deadline, link, email_date, status, is_ghost)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (telegram_id, cycle_id, source_application_id, gmail_id,
                 task_type, company, company_n, role, role_n,
                 deadline, link, email_date, status, is_ghost),
            )
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None


def get_task_by_id(task_id: int) -> Optional[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()


def get_assessment_tasks(telegram_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """SELECT * FROM tasks
               WHERE telegram_id = ? AND status = 'incomplete' AND is_ghost = 0
               AND type IN ('oa', 'hirevue', 'interview')
               ORDER BY
                 CASE WHEN deadline IS NULL THEN 1 ELSE 0 END,
                 deadline ASC,
                 CASE type
                   WHEN 'interview' THEN 0
                   WHEN 'hirevue'   THEN 1
                   WHEN 'oa'        THEN 2
                 END ASC""",
            (telegram_id,),
        ).fetchall()


def get_applications(telegram_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """SELECT * FROM tasks
               WHERE telegram_id = ? AND type = 'application' AND is_ghost = 0
               ORDER BY created_at DESC""",
            (telegram_id,),
        ).fetchall()


def get_applications_by_status(telegram_id: int, status: str) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """SELECT * FROM tasks
               WHERE telegram_id = ? AND type = 'application' AND is_ghost = 0
               AND status = ?
               ORDER BY updated_at DESC, created_at DESC""",
            (telegram_id, status),
        ).fetchall()


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


def get_all_incomplete_tasks_for_all_users() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """SELECT * FROM tasks
               WHERE status = 'incomplete' AND is_ghost = 0
               ORDER BY telegram_id, deadline ASC NULLS LAST""",
        ).fetchall()


def mark_done(task_id: int) -> None:
    mark_status(task_id, "done")


def mark_status(task_id: int, status: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE tasks SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, task_id),
        )


def promote_ghost_application(task_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            """UPDATE tasks
               SET is_ghost = 0, updated_at = CURRENT_TIMESTAMP
               WHERE id = ? AND type = 'application' AND is_ghost = 1""",
            (task_id,),
        )


def merge_application_email(
    task_id: int,
    gmail_id: str,
    company: str,
    role: str,
    email_date: Optional[str] = None,
) -> None:
    company_n = _normalise(company)
    role_n = _normalise(role)

    with get_connection() as conn:
        conn.execute(
            """UPDATE tasks
               SET gmail_id = COALESCE(gmail_id, ?),
                   company = ?,
                   company_normalised = ?,
                   role = ?,
                   role_normalised = ?,
                   email_date = CASE
                       WHEN ? IS NULL THEN email_date
                       WHEN email_date IS NULL THEN ?
                       WHEN email_date > ? THEN ?
                       ELSE email_date
                   END,
                   is_ghost = 0,
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (
                gmail_id,
                company,
                company_n,
                role,
                role_n,
                email_date,
                email_date,
                email_date,
                email_date,
                task_id,
            ),
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
    company: str,
    role: str,
    task_type: str,
    deadline: Optional[str],
    cycle_id: Optional[int] = None,
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


def get_cycle_stats(telegram_id: int, cycle_id: int) -> dict:
    with get_connection() as conn:
        applied = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE telegram_id = ? AND cycle_id = ? AND type = 'application' AND is_ghost = 0",
            (telegram_id, cycle_id),
        ).fetchone()[0]

        interviewing = conn.execute(
            """SELECT COUNT(DISTINCT source_application_id) FROM tasks
               WHERE telegram_id = ? AND cycle_id = ?
               AND type IN ('oa', 'hirevue', 'interview') AND status = 'incomplete'
               AND source_application_id IS NOT NULL""",
            (telegram_id, cycle_id),
        ).fetchone()[0]

        offered = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE telegram_id = ? AND cycle_id = ? AND type = 'application' AND is_ghost = 0 AND status = 'offer'",
            (telegram_id, cycle_id),
        ).fetchone()[0]

        rejected = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE telegram_id = ? AND cycle_id = ? AND type = 'application' AND is_ghost = 0 AND status = 'rejected'",
            (telegram_id, cycle_id),
        ).fetchone()[0]

        # Ghosted = real applications still incomplete with no linked follow-up tasks
        ghosted = conn.execute(
            """SELECT COUNT(*) FROM tasks app
               WHERE app.telegram_id = ? AND app.cycle_id = ?
               AND app.type = 'application' AND app.is_ghost = 0 AND app.status = 'incomplete'
               AND NOT EXISTS (SELECT 1 FROM tasks t WHERE t.source_application_id = app.id)""",
            (telegram_id, cycle_id),
        ).fetchone()[0]

        pending = conn.execute(
            """SELECT COUNT(*) FROM tasks WHERE telegram_id = ? AND cycle_id = ?
               AND type IN ('oa', 'hirevue', 'interview') AND status = 'incomplete'""",
            (telegram_id, cycle_id),
        ).fetchone()[0]

        responded = conn.execute(
            """SELECT COUNT(DISTINCT source_application_id) FROM tasks
               WHERE telegram_id = ? AND cycle_id = ?
               AND type IN ('oa', 'hirevue', 'interview')
               AND source_application_id IS NOT NULL""",
            (telegram_id, cycle_id),
        ).fetchone()[0]

        avg_days_raw = conn.execute(
            """SELECT AVG(julianday(t.created_at) - julianday(app.created_at))
               FROM tasks t
               JOIN tasks app ON t.source_application_id = app.id
               WHERE t.telegram_id = ? AND t.cycle_id = ?
               AND t.type IN ('oa', 'hirevue', 'interview')""",
            (telegram_id, cycle_id),
        ).fetchone()[0]

        return {
            "applied": applied,
            "interviewing": interviewing,
            "offered": offered,
            "rejected": rejected,
            "ghosted": ghosted,
            "pending": pending,
            "response_rate": round(responded / applied * 100) if applied else 0,
            "offer_rate": round(offered / applied * 100, 1) if applied else 0,
            "avg_days": round(avg_days_raw) if avg_days_raw else 0,
        }


def get_user_stats(telegram_id: int) -> dict:
    with get_connection() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE telegram_id = ? AND type = 'application' AND is_ghost = 0",
            (telegram_id,),
        ).fetchone()[0]

        responded = conn.execute(
            """SELECT COUNT(DISTINCT source_application_id) FROM tasks
               WHERE telegram_id = ? AND type IN ('oa', 'hirevue', 'interview')
               AND source_application_id IS NOT NULL""",
            (telegram_id,),
        ).fetchone()[0]

        offers = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE telegram_id = ? AND type = 'application' AND is_ghost = 0 AND status = 'offer'",
            (telegram_id,),
        ).fetchone()[0]

        this_week = conn.execute(
            """SELECT COUNT(*) FROM tasks
               WHERE telegram_id = ? AND type = 'application' AND is_ghost = 0
               AND created_at >= datetime('now', '-7 days')""",
            (telegram_id,),
        ).fetchone()[0]

        this_month = conn.execute(
            """SELECT COUNT(*) FROM tasks
               WHERE telegram_id = ? AND type = 'application' AND is_ghost = 0
               AND created_at >= datetime('now', '-30 days')""",
            (telegram_id,),
        ).fetchone()[0]

        pending = conn.execute(
            """SELECT COUNT(*) FROM tasks
               WHERE telegram_id = ? AND status = 'incomplete' AND is_ghost = 0
               AND type IN ('oa', 'hirevue', 'interview')""",
            (telegram_id,),
        ).fetchone()[0]

        return {
            "total": total,
            "responded": responded,
            "response_rate": round(responded / total * 100) if total else 0,
            "offers": offers,
            "offer_rate": round(offers / total * 100) if total else 0,
            "this_week": this_week,
            "this_month": this_month,
            "pending": pending,
        }
