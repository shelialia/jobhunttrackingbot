import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "data/jobtracker.db")


def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                email TEXT,
                gmail_token_json TEXT,
                last_scanned_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL REFERENCES users(telegram_id),
                source_application_id INTEGER REFERENCES tasks(id),
                gmail_id TEXT,
                type TEXT NOT NULL,
                company TEXT,
                company_normalised TEXT,
                role TEXT,
                role_normalised TEXT,
                deadline TIMESTAMP,
                link TEXT,
                email_date TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'incomplete',
                is_ghost INTEGER NOT NULL DEFAULT 0,
                nudged_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_gmail_id
                ON tasks(telegram_id, gmail_id) WHERE gmail_id IS NOT NULL;

            CREATE INDEX IF NOT EXISTS idx_tasks_lookup
                ON tasks(telegram_id, company_normalised, role_normalised, type, status);

            CREATE INDEX IF NOT EXISTS idx_tasks_deadline
                ON tasks(telegram_id, status, deadline);
        """)
        # migration: add email_date if it doesn't exist yet
        cols = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
        if "email_date" not in cols:
            conn.execute("ALTER TABLE tasks ADD COLUMN email_date TIMESTAMP")
