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


def _as_datetime(value) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


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


def find_existing_application(
    telegram_id: int,
    company: str,
    role: str,
    cycle_id: Optional[int] = None,
    include_ghost: bool = True,
) -> Optional[int]:
    return _find_matching_application(
        telegram_id, company, role, cycle_id=cycle_id, include_ghost=include_ghost
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
    interview_round: Optional[int] = None,
    is_final_round: int = 0,
    round_label: Optional[str] = None,
    interview_date: Optional[str] = None,
    interview_platform: Optional[str] = None,
    confirmed_at: Optional[str] = None,
) -> Optional[int]:
    company_n = _normalise(company)
    role_n = _normalise(role)

    with get_connection() as conn:
        try:
            cursor = conn.execute(
                """INSERT INTO tasks
                   (telegram_id, cycle_id, source_application_id, gmail_id, type,
                    company, company_normalised, role, role_normalised,
                    interview_round, is_final_round, round_label, deadline,
                    interview_date, interview_platform, confirmed_at, link,
                    email_date, status, is_ghost)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (telegram_id, cycle_id, source_application_id, gmail_id,
                 task_type, company, company_n, role, role_n,
                 interview_round, is_final_round, round_label, deadline,
                 interview_date, interview_platform, confirmed_at, link,
                 email_date, status, is_ghost),
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
    deadline: Optional[str] = None,
    link: Optional[str] = None,
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
                   deadline = COALESCE(deadline, ?),
                   link = COALESCE(link, ?),
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
                deadline,
                link,
                email_date,
                email_date,
                email_date,
                email_date,
                task_id,
            ),
        )


def find_existing_interview(
    telegram_id: int,
    cycle_id: int,
    company: str,
    interview_round: Optional[int] = None,
) -> Optional[sqlite3.Row]:
    company_n = _normalise(company)

    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM tasks
               WHERE telegram_id = ? AND cycle_id = ?
               AND type = 'interview'
               AND company_normalised = ?
               ORDER BY created_at DESC""",
            (telegram_id, cycle_id, company_n),
        ).fetchall()

    if interview_round is not None:
        for row in rows:
            if row["interview_round"] == interview_round:
                return row
        return None

    cutoff = datetime.utcnow() - timedelta(days=7)
    for row in rows:
        created_at = _as_datetime(row["created_at"])
        if created_at and created_at >= cutoff:
            return row
    return None


def update_interview_task(
    task_id: int,
    *,
    gmail_id: Optional[str] = None,
    source_application_id: Optional[int] = None,
    company: Optional[str] = None,
    role: Optional[str] = None,
    deadline: Optional[str] = None,
    link: Optional[str] = None,
    email_date: Optional[str] = None,
    interview_round: Optional[int] = None,
    is_final_round: Optional[int] = None,
    round_label: Optional[str] = None,
    interview_date: Optional[str] = None,
    interview_platform: Optional[str] = None,
    confirmed_at: Optional[str] = None,
) -> None:
    company_value = company if company else None
    role_value = role if role else None
    company_n = _normalise(company_value) if company_value else None
    role_n = _normalise(role_value) if role_value else None

    with get_connection() as conn:
        conn.execute(
            """UPDATE tasks
               SET gmail_id = COALESCE(gmail_id, ?),
                   is_ghost = CASE WHEN ? IS NOT NULL THEN 0 ELSE is_ghost END,
                   source_application_id = COALESCE(source_application_id, ?),
                   company = COALESCE(?, company),
                   company_normalised = CASE
                       WHEN ? IS NOT NULL THEN ?
                       ELSE company_normalised
                   END,
                   role = COALESCE(?, role),
                   role_normalised = CASE
                       WHEN ? IS NOT NULL THEN ?
                       ELSE role_normalised
                   END,
                   interview_round = COALESCE(?, interview_round),
                   is_final_round = COALESCE(?, is_final_round),
                   round_label = COALESCE(?, round_label),
                   deadline = COALESCE(?, deadline),
                   interview_date = COALESCE(?, interview_date),
                   interview_platform = COALESCE(?, interview_platform),
                   confirmed_at = COALESCE(?, confirmed_at),
                   link = COALESCE(?, link),
                   email_date = CASE
                       WHEN ? IS NULL THEN email_date
                       WHEN email_date IS NULL THEN ?
                       WHEN email_date > ? THEN ?
                       ELSE email_date
                   END,
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (
                gmail_id,
                gmail_id,
                source_application_id,
                company_value,
                company_n,
                company_n,
                role_value,
                role_n,
                role_n,
                interview_round,
                is_final_round,
                round_label,
                deadline,
                interview_date,
                interview_platform,
                confirmed_at,
                link,
                email_date,
                email_date,
                email_date,
                email_date,
                task_id,
            ),
        )


def get_root_application_id(task_id: int) -> Optional[int]:
    current_id = task_id

    with get_connection() as conn:
        while current_id is not None:
            row = conn.execute(
                "SELECT id, type, source_application_id FROM tasks WHERE id = ?",
                (current_id,),
            ).fetchone()
            if row is None:
                return None
            if row["type"] == "application":
                return row["id"]
            current_id = row["source_application_id"]

    return None


def count_interviews_in_chain(root_application_id: int) -> int:
    with get_connection() as conn:
        return conn.execute(
            """WITH RECURSIVE chain AS (
                   SELECT id, type FROM tasks WHERE id = ?
                   UNION ALL
                   SELECT t.id, t.type
                   FROM tasks t
                   JOIN chain c ON t.source_application_id = c.id
               )
               SELECT COUNT(*) FROM chain WHERE type = 'interview'""",
            (root_application_id,),
        ).fetchone()[0]


def get_interview_by_round(root_application_id: int, interview_round: int) -> Optional[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """WITH RECURSIVE chain AS (
                   SELECT * FROM tasks WHERE id = ?
                   UNION ALL
                   SELECT t.*
                   FROM tasks t
                   JOIN chain c ON t.source_application_id = c.id
               )
               SELECT * FROM chain
               WHERE type = 'interview' AND interview_round = ?
               ORDER BY is_ghost ASC, created_at ASC
               LIMIT 1""",
            (root_application_id, interview_round),
        ).fetchone()


def create_ghost_interview(
    telegram_id: int,
    cycle_id: int,
    source_application_id: int,
    company: str,
    role: str,
    interview_round: int,
) -> Optional[int]:
    return insert_task(
        telegram_id=telegram_id,
        gmail_id=None,
        task_type="interview",
        company=company,
        role=role,
        deadline=None,
        link=None,
        source_application_id=source_application_id,
        is_ghost=1,
        email_date=None,
        cycle_id=cycle_id,
        status="incomplete",
        interview_round=interview_round,
        is_final_round=0,
        round_label=None,
        interview_date=None,
        interview_platform=None,
        confirmed_at=None,
    )


def ensure_interview_chain(
    telegram_id: int,
    cycle_id: int,
    root_application_id: int,
    company: str,
    role: str,
    interview_round: int,
) -> Optional[int]:
    if interview_round <= 1:
        return root_application_id

    previous = get_interview_by_round(root_application_id, interview_round - 1)
    if previous is not None:
        return previous["id"]

    parent_id = ensure_interview_chain(
        telegram_id,
        cycle_id,
        root_application_id,
        company,
        role,
        interview_round - 1,
    )
    if parent_id is None:
        return None

    ghost_id = create_ghost_interview(
        telegram_id,
        cycle_id,
        parent_id,
        company,
        role,
        interview_round - 1,
    )
    return ghost_id


def get_cycle_applications(telegram_id: int, cycle_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """SELECT * FROM tasks
               WHERE telegram_id = ? AND cycle_id = ?
               AND type = 'application' AND is_ghost = 0
               ORDER BY created_at DESC""",
            (telegram_id, cycle_id),
        ).fetchall()


def get_chain_rows(root_application_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """WITH RECURSIVE chain AS (
                   SELECT * FROM tasks WHERE id = ?
                   UNION ALL
                   SELECT t.*
                   FROM tasks t
                   JOIN chain c ON t.source_application_id = c.id
               )
               SELECT * FROM chain
               ORDER BY COALESCE(email_date, created_at) ASC, id ASC""",
            (root_application_id,),
        ).fetchall()


def _get_cycle_chain_rows(telegram_id: int, cycle_id: int) -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            """WITH RECURSIVE chain AS (
                   SELECT
                       id,
                       id AS root_id,
                       type,
                       source_application_id,
                       company,
                       role,
                       cycle_id,
                       interview_round,
                       is_final_round,
                       deadline,
                       status,
                       is_ghost,
                       email_date,
                       created_at
                   FROM tasks
                   WHERE type = 'application'
                     AND is_ghost = 0
                     AND cycle_id = ?
                     AND telegram_id = ?
                   UNION ALL
                   SELECT
                       t.id,
                       c.root_id,
                       t.type,
                       t.source_application_id,
                       t.company,
                       t.role,
                       t.cycle_id,
                       t.interview_round,
                       t.is_final_round,
                       t.deadline,
                       t.status,
                       t.is_ghost,
                       t.email_date,
                       t.created_at
                   FROM tasks t
                   JOIN chain c ON t.source_application_id = c.id
                   WHERE t.type != 'irrelevant'
               )
               SELECT * FROM chain""",
            (cycle_id, telegram_id),
        ).fetchall()


def get_sankey_edges(telegram_id: int, cycle_id: int) -> list[tuple[str, str, int]]:
    with get_connection() as conn:
        rows = conn.execute(
            """WITH RECURSIVE chain AS (
                   SELECT
                       id,
                       id AS root_id,
                       type,
                       source_application_id
                   FROM tasks
                   WHERE type = 'application'
                     AND is_ghost = 0
                     AND cycle_id = ?
                     AND telegram_id = ?
                   UNION ALL
                   SELECT
                       t.id,
                       c.root_id,
                       t.type,
                       t.source_application_id
                   FROM tasks t
                   JOIN chain c ON t.source_application_id = c.id
                   WHERE t.type != 'irrelevant'
               )
               SELECT p.type AS source, c.type AS target, COUNT(*) AS flow
               FROM chain c
               JOIN chain p ON c.source_application_id = p.id AND c.root_id = p.root_id
               WHERE c.type != 'irrelevant'
               GROUP BY p.type, c.type
               ORDER BY p.type, c.type""",
            (cycle_id, telegram_id),
        ).fetchall()
    return [(row["source"], row["target"], row["flow"]) for row in rows]


def get_interview_breakdown(telegram_id: int, cycle_id: int) -> dict:
    rows = _get_cycle_chain_rows(telegram_id, cycle_id)
    apps = {row["id"]: row for row in rows if row["type"] == "application"}
    chains: dict[int, list[sqlite3.Row]] = {app_id: [] for app_id in apps}

    for row in rows:
        chains.setdefault(row["root_id"], []).append(row)

    total_rounds = 0
    leaderboard: list[dict] = []
    buckets = {"1 round": 0, "2-3 rounds": 0, "4+ rounds": 0}

    for app_id, chain_rows in chains.items():
        interview_rows = [row for row in chain_rows if row["type"] == "interview"]
        if not interview_rows:
            continue

        max_round = max((row["interview_round"] or 0) for row in interview_rows)
        total_rounds += max_round

        if max_round == 1:
            buckets["1 round"] += 1
        elif 2 <= max_round <= 3:
            buckets["2-3 rounds"] += 1
        else:
            buckets["4+ rounds"] += 1

        outcome = "ongoing"
        if any(row["type"] == "offer" for row in chain_rows) or apps[app_id]["status"] == "offer":
            outcome = "offer"
        elif any(row["type"] == "rejection" for row in chain_rows) or apps[app_id]["status"] == "rejected":
            outcome = "rejected"

        leaderboard.append(
            {
                "app_id": app_id,
                "company": apps[app_id]["company"] or "Unknown",
                "rounds": max_round,
                "outcome": outcome,
            }
        )

    leaderboard.sort(key=lambda row: (-row["rounds"], row["company"].lower()))

    return {
        "total_rounds": total_rounds,
        "leaderboard": leaderboard[:3],
        "buckets": buckets,
    }

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
    now_iso = datetime.utcnow().isoformat()
    interview_breakdown = get_interview_breakdown(telegram_id, cycle_id)
    chain_rows = _get_cycle_chain_rows(telegram_id, cycle_id)
    now_dt = _as_datetime(now_iso)
    interviewing_roots = {
        row["root_id"]
        for row in chain_rows
        if row["type"] == "interview"
        and row["status"] == "incomplete"
        and row["root_id"] is not None
        and (deadline_dt := _as_datetime(row["deadline"])) is not None
        and deadline_dt >= now_dt
    }
    with get_connection() as conn:
        applied = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE telegram_id = ? AND cycle_id = ? AND type = 'application' AND is_ghost = 0",
            (telegram_id, cycle_id),
        ).fetchone()[0]

        interviewing = len(interviewing_roots)

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
            "response_rate": round(responded / applied * 100) if applied else 0,
            "offer_rate": round(offered / applied * 100, 1) if applied else 0,
            "avg_days": round(avg_days_raw) if avg_days_raw else 0,
            "total_interview_rounds": interview_breakdown["total_rounds"],
            "round_leaderboard": interview_breakdown["leaderboard"],
            "interview_depth_buckets": interview_breakdown["buckets"],
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
