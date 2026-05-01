# Job Hunt Tracker Bot

A self-hosted Telegram bot that scans Gmail for job application updates, classifies them with an LLM, stores the workflow in SQLite, and gives you a compact command-based view of your funnel.

This project is designed for open-source + BYOK use:
- bring your own Telegram bot token
- bring your own Google OAuth credentials
- bring your own Gemini API key
- run your own bot instance and keep your own Gmail tokens/data

---

## What it does

- Scans Gmail for:
  - application confirmations
  - online assessments
  - HireVue / one-way video interviews
  - live interview invites
  - offers
  - rejections
- Builds a linked application chain in SQLite:
  - `application -> oa -> interview -> offer`
  - `application -> interview -> rejection`
  - etc.
- Deduplicates repeated scans by Gmail message id
- Creates ghost application anchors when a follow-up email arrives before the original application confirmation
- Tracks interview rounds, final rounds, interview dates, and platforms
- Sends a daily digest
- Exposes Telegram commands for tasks, stats, timelines, and a funnel Sankey diagram

---

## Current command surface

Visible Telegram commands:

- `/start` - set up your account
- `/connect` - connect Gmail
- `/scan` - manually scan Gmail now
- `/tasks` - pending assessments and interviews
- `/applied` - all applications in the active cycle
- `/timeline <app_number>` - full chain for one application
- `/upcoming` - items due in the next 7 days
- `/stats` - active-cycle stats
- `/sankey` - export funnel Sankey diagram
- `/done <task_number>` - mark a task done
- `/offer <app_number>` - mark an application as offered
- `/reject <app_number>` - mark an application as rejected
- `/remove <task_number or app_number>` - delete an application or task
- `/add <company> [date] [type]` - add a task manually
- `/cycles` - view cycles
- `/newcycle` - start a new cycle
- `/switchcycle` - switch cycles
- `/help`

Internal confirmation flows still use `/confirm`, but it is not advertised in the command menu.

---

## Features

- Gmail OAuth login flow with local Flask callback server
- BYOK LLM classification using `gemma-4-31b-it`
- Manual scan summary grouped into:
  - applications submitted
  - pending assessments
  - interviews
  - offers / rejections when present
- Daily digest with the same grouping
- Interview chain tracking:
  - round number
  - final-round flag
  - round label
  - confirmed interview datetime
  - interview platform
- `/timeline` output for one application chain
- `/sankey` PNG export with:
  - application / OA / HireVue / interview-round / offer / rejection / ghosted / pending nodes
- Safe chunking for long bot outputs so large lists do not exceed Telegram message limits
- Singapore-time reminder labels for:
  - `TODAY`
  - `Xd remaining`
  - `OVERDUE`

---

## Tech stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| Telegram | python-telegram-bot v20 |
| Scheduler | APScheduler 3.x |
| Email | Gmail API |
| LLM client | `google-generativeai` |
| Model | `gemma-4-31b-it` |
| Database | SQLite |
| OAuth callback | Flask |
| Diagram export | Plotly + Kaleido |

---

## Prerequisites

You need credentials from three services.

### 1. Telegram bot token

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Run `/newbot`
3. Copy the token as `TELEGRAM_BOT_TOKEN`

### 2. Google OAuth credentials

The bot reads Gmail through OAuth 2.0.

1. Create a project in Google Cloud Console
2. Enable the Gmail API
3. Create an OAuth client id of type **Web application**
4. Add an authorized redirect URI:
   - local dev: `http://localhost:5001/oauth/callback`
   - self-hosted: `http://YOUR_HOST:5001/oauth/callback`
5. Copy:
   - `GOOGLE_CLIENT_ID`
   - `GOOGLE_CLIENT_SECRET`
6. Add your Gmail account as a test user if the app is still in testing mode

### 3. Gemini API key

1. Go to Google AI Studio
2. Create an API key
3. Use it as `GEMINI_API_KEY`

---

## Local setup

```bash
git clone https://github.com/shelialia/jobhunttrackingbot.git
cd jobhunttrackingbot

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `.env`:

```bash
cp .env.example .env
```

Example values:

```env
TELEGRAM_BOT_TOKEN=your_telegram_token
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
OAUTH_REDIRECT_URI=http://localhost:5001/oauth/callback
GEMINI_API_KEY=your_gemini_api_key
DB_PATH=data/jobtracker.db
FLASK_DEBUG=false
```

Run two processes.

Terminal 1:

```bash
python -m jobtracker.oauth_server.app
```

Terminal 2:

```bash
python -m jobtracker.bot.main
```

Then open Telegram and run `/start`.

---

## Self-hosting

You can run the same two processes on a spare laptop, VM, or home server.

Example with `nohup`:

```bash
nohup python -m jobtracker.oauth_server.app > logs/oauth.log 2>&1 &
nohup python -m jobtracker.bot.main > logs/bot.log 2>&1 &
```

Example with PM2:

```bash
npm install -g pm2
pm2 start "python -m jobtracker.oauth_server.app" --name oauth
pm2 start "python -m jobtracker.bot.main" --name bot
pm2 save
pm2 startup
```

If your OAuth callback is not reachable directly, expose port `5001` with a tunnel such as ngrok and update `OAUTH_REDIRECT_URI`.

---

## How scanning works

### Scan window

- First manual `/scan` for a new cycle:
  - scans the last 14 days
- Later scans:
  - use `max(last_scan_timestamp, now - 24 hours)`
- Both manual scans and auto scans write the latest successful scan timestamp back to the database

### Scan pipeline

1. Fetch Gmail messages since the current scan window start
2. Parse subject, body, Gmail id, and email date
3. Classify each email with the LLM into structured JSON
4. Skip `irrelevant`
5. Link the email into the existing application chain
6. Insert or update the right task row
7. Send a grouped scan summary back to Telegram

### Linking rules

- application confirmations create or update the root application row
- OA / HireVue / interview / offer / rejection follow-ups attach to the latest relevant stage in the existing chain when possible
- if no application exists yet, a ghost application anchor is created
- interview confirmations update the existing round instead of creating a new round

---

## Data model

The main table is `tasks`. It stores both:
- root application rows
- follow-up task/event rows

Important fields:

- `type`
  - `application`
  - `oa`
  - `hirevue`
  - `interview`
  - `offer`
  - `rejection`
- `source_application_id`
  - parent pointer used to build the chain
- `is_ghost`
  - marks inferred application/interview anchors
- `interview_round`
- `is_final_round`
- `round_label`
- `interview_date`
- `interview_platform`
- `confirmed_at`

Example chain:

```text
application
  -> oa
    -> interview round 1
      -> interview round 2
        -> offer
```

---

## Output behavior

### `/tasks`

Sorted in this order:
1. unscheduled
2. overdue
3. future scheduled items by soonest date

For interviews:
- no confirmed interview time -> `UNSCHEDULED`
- confirmed interview time -> uses `interview_date`

### `/upcoming`

Shows incomplete items due within the next 7 days.

For interviews:
- uses `interview_date`
- unscheduled interviews do not appear there

### `/timeline`

Shows one application chain in chronological order.

Examples:
- `✅ Applied`
- `📝 OA`
- `📞 Round 1: Phone Screen`
- `🏁 Round 2: Final Round`
- `🎉 Offer`
- `❌ Rejection`

### `/sankey`

Exports a PNG funnel diagram.

Interview rounds render as separate nodes:
- `1st Interview`
- `2nd Interview`
- `3rd Interview`

Terminal nodes include:
- `Offer`
- `Rejection`
- `Ghosted`
- `Pending`

---

## Project structure

```text
jobtracker/
├── bot/
│   ├── main.py
│   ├── message_utils.py
│   ├── time_utils.py
│   ├── commands/
│   ├── db/
│   ├── gmail/
│   ├── llm/
│   └── scheduler/
└── oauth_server/
```

---

## Known behavior and constraints

- LLM calls are synchronous on purpose right now
- there is an explicit inter-email sleep in scan flow to stay within low-cost usage
- reminder labels are shown in Singapore time
- the daily digest job is scheduled at `01:00` in the host machine's scheduler timezone
- this is designed for self-hosted/BYOK use, not a hosted multi-tenant SaaS

---

## Contributing

Contributions are welcome, but the project is opinionated in a few places:

- privacy-sensitive flows should stay self-host friendly
- dedup/linking behavior matters more than cosmetic refactors
- follow-up stages should attach to the latest valid chain stage
- interview confirmation emails should update the existing round, not create new ones

If you open a PR, describe:
- the bug
- the expected chain behavior
- the before/after DB shape if the fix affects linking

For current engineering notes, testing coverage, bug history, and planned work, see [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

---

## License

MIT
