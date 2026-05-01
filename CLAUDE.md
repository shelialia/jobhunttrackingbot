# CLAUDE.md — Job Hunt Tracker Telegram Bot

Before you start building, create a new repository on Github and make frequent granular commits as you work on the project. 

## Project overview

A Telegram bot that monitors a user's Gmail inbox for job application to-dos (OAs,
HireVues, Codility, HackerRank, interview invites), stores them in SQLite, and sends
a daily digest + urgent deadline nudges via Telegram.

---

## Stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| Telegram | python-telegram-bot v20+ (async) |
| Scheduler | APScheduler 3.x |
| Email | Gmail API — google-auth-oauthlib, google-api-python-client |
| LLM | Gemini Flash 2.0 (free tier, 1500 req/day) |
| Database | SQLite via stdlib sqlite3 |
| OAuth callback | Flask (same VPS, separate process) |
| Fuzzy matching | rapidfuzz (post-MVP only) |
| Deployment | DigitalOcean $4/mo droplet or Raspberry Pi |

---

## Project structure

```
jobtracker/
├── bot/
│   ├── main.py              # entry point — starts bot + scheduler
│   ├── commands/
│   │   ├── start.py         # /start onboarding
│   │   ├── connect.py       # /connect Gmail OAuth flow
│   │   ├── tasks.py         # /tasks pending assessments + interviews
│   │   ├── applied.py       # /applied all applications
│   │   ├── upcoming.py      # /upcoming next 7 days
│   │   ├── stats.py         # /stats job hunt statistics
│   │   ├── scan.py          # /scan manual Gmail poll
│   │   ├── done.py          # /done [company]
│   │   ├── offer.py         # /offer [company]
│   │   ├── reject.py        # /reject [company]
│   │   ├── add.py           # /add [company] [deadline]
│   │   ├── remove.py        # /remove [company]
│   │   └── help.py          # /help
│   ├── scheduler/
│   │   ├── digest.py        # daily 9AM UTC digest job
│   │   └── nudge.py         # hourly 24h deadline nudge job
│   ├── gmail/
│   │   ├── auth.py          # OAuth2 URL generation + token refresh
│   │   ├── fetch.py         # Gmail API fetch since last_scanned_at
│   │   └── parse.py         # extract subject + body from raw message
│   ├── llm/
│   │   └── classify.py      # Gemini call — classify email, extract fields
│   └── db/
│       ├── schema.py        # CREATE TABLE statements + migrations
│       ├── users.py         # user CRUD
│       └── tasks.py         # task CRUD + dedup + linking logic
├── oauth_server/
│   └── app.py               # Flask callback — receives OAuth code from Google
├── data/
│   └── jobtracker.db        # SQLite file (gitignored)
├── credentials.json         # Google OAuth client secret (gitignored)
├── .env                     # secrets (gitignored)
├── requirements.txt
└── CLAUDE.md
```

---

## Database schema

### users
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| telegram_id | INTEGER UNIQUE | from Telegram update |
| email | TEXT | user's Gmail address |
| gmail_token_json | TEXT | serialised OAuth2 token blob |
| last_scanned_at | TIMESTAMP | updated after every scan |
| created_at | TIMESTAMP | |

### tasks
| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| telegram_id | INTEGER FK | |
| source_application_id | INTEGER FK | self-ref — links OA/HireVue/interview back to its application row |
| gmail_id | TEXT | raw Gmail message ID — dedup key (nullable for ghosts) |
| type | TEXT | application \| oa \| hirevue \| interview |
| company | TEXT | raw, as extracted by LLM — for display |
| company_normalised | TEXT | output of normalise(company) — for matching |
| role | TEXT | raw |
| role_normalised | TEXT | output of normalise(role) — for matching |
| deadline | TIMESTAMP | |
| link | TEXT | direct assessment/interview URL if found |
| status | TEXT | incomplete \| done |
| is_ghost | INTEGER | 1 = inferred application with no confirmation email |
| nudged_at | TIMESTAMP | set when 24h nudge fires — prevents repeat nudges |
| updated_at | TIMESTAMP | used to compute "completed this week" |
| created_at | TIMESTAMP | |

**Key indexes:**
```sql
CREATE UNIQUE INDEX idx_tasks_gmail_id
    ON tasks(telegram_id, gmail_id) WHERE gmail_id IS NOT NULL;

CREATE INDEX idx_tasks_lookup
    ON tasks(telegram_id, company_normalised, role_normalised, type, status);

CREATE INDEX idx_tasks_deadline
    ON tasks(telegram_id, status, deadline);
```

---

## Core logic

### Email scan pipeline (shared by /scan and background poller)
1. Fetch emails from Gmail API since `last_scanned_at` using `after:{unix_timestamp}`
2. For each message: check `gmail_id` against tasks table — skip if already processed
3. Extract subject + body from raw Gmail message payload
4. Send subject + body to Gemini — get back structured JSON (type, company, role, deadline, link)
5. If type is `oa | hirevue | interview`: call `find_or_create_application()` to get `source_application_id`
6. Insert task row with `company_normalised = normalise(company)`, `role_normalised = normalise(role)`
7. Update `users.last_scanned_at = now()`

### Deduplication — two separate problems
- **Same email processed twice:** blocked by unique index on `(telegram_id, gmail_id)`
- **Linking related emails:** `find_application_for_linking()` looks up an existing `application`
  row matching `company_normalised` (exact) + `role_normalised` (rapidfuzz partial_ratio ≥ 80) within 90 days.
  If not found, inserts a ghost application row (`is_ghost = 1`) as an anchor.

### normalise(text)
Lowercases, strips punctuation, collapses whitespace, removes common legal suffixes
(inc, ltd, llc, corp, limited, co). Used for both storage and lookup — never shown to users.

```python
import re

def normalise(text: str) -> str:
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    for suffix in ["inc", "ltd", "llc", "corp", "limited", "co"]:
        text = re.sub(rf"\b{suffix}\b", "", text).strip()
    return text
```

### Scheduler jobs
- **Daily digest** — `CronTrigger(hour=1, minute=0)` (01:00 UTC = 09:00 SGT)
  Fetches all incomplete tasks for all users, sorted by deadline asc, sends digest message.
  Skips users with no pending tasks.

- **Hourly nudge** — `IntervalTrigger(hours=1)`
  Finds tasks where `deadline BETWEEN now() AND now() + 24h`
  AND `status = 'incomplete'` AND `nudged_at IS NULL`.
  Fires one nudge message per task, sets `nudged_at = now()`.

### Task sort order (for /status and digest)
Primary: `days_remaining ASC` (overdue tasks are negative — float to top naturally).
Secondary: type priority — `interview (0) > hirevue (1) > oa (2)` as tiebreaker.

### Stats computation
- `total_applied` — `type = 'application' AND is_ghost = 0`
- `response_rate` — distinct `source_application_id` values across non-application tasks / total_applied
- `this_week` / `this_month` — applications created within last 7 / 30 days
- `pending` — incomplete OA/HireVue/interview tasks

---

## Bot commands

| Command | Description |
|---|---|
| `/start` | Onboard user, show privacy notice, prompt /connect |
| `/connect` | Generate Gmail OAuth2 URL, send to user |
| `/tasks` | Pending assessments and interviews sorted by urgency |
| `/applied` | All submitted applications |
| `/upcoming` | Tasks due in the next 7 days |
| `/stats` | Job hunt stats — applied, response rate, pending |
| `/scan` | Trigger immediate Gmail poll, reply with newly found tasks |
| `/done [company]` | Mark matching incomplete task as done |
| `/offer [company]` | Mark an application as an offer |
| `/reject [company]` | Mark an application as rejected |
| `/add [company] [deadline]` | Manually insert a task the bot missed |
| `/remove [company]` | Delete a wrongly detected task |
| `/help` | List all commands |

---

## Environment variables (.env)

```
TELEGRAM_BOT_TOKEN=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
OAUTH_REDIRECT_URI=https://yourserver.com/oauth/callback
GEMINI_API_KEY=
DB_PATH=data/jobtracker.db
```

---

## LLM prompt contract

Gemini is called once per email. The prompt must instruct it to return **only valid JSON**
with no preamble or markdown fences. Expected output shape:

```json
{
  "type": "oa | hirevue | interview | application | irrelevant",
  "company": "Stripe",
  "role": "Software Engineer Intern",
  "deadline": "2025-05-03T23:59:00",
  "link": "https://app.codility.com/...",
  "confidence": 0.95
}
```

- `type = "irrelevant"` means the email is not job-related — skip it, do not insert.
- `deadline` is ISO 8601 or null if not found.
- `link` is null if no direct URL found in the body.
- `confidence` below 0.7 should trigger a Telegram message asking the user to confirm.

---

## Gmail API notes

- Scope required: `https://www.googleapis.com/auth/gmail.readonly`
- Always use `access_type="offline"` and `prompt="consent"` when generating the auth URL
  to ensure a refresh token is returned.
- Store the full token blob as JSON in `users.gmail_token_json` — do not split into columns.
- The `after:` query param takes Unix epoch seconds, not an ISO string:
  `int(last_scanned_at.timestamp())`
- Dedup at DB level via unique index on `gmail_id` — do not rely solely on application logic.

---

## What is not in the MVP

- Per-user notification time (hardcoded 01:00 UTC for now)
- Timezone support
- Deadline nudges — `scheduler/nudge.py` exists but is not registered in the scheduler; `get_all_tasks_due_soon()` and `mark_nudged()` are missing from `db/tasks.py`
- Multi-email provider support (Outlook etc.)
- Web dashboard