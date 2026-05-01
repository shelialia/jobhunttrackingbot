# Job Hunt Tracker Bot

A Telegram bot that monitors your Gmail inbox for job application to-dos — online assessments, HireVues, interview invites — stores them in SQLite, and sends a daily digest and urgent deadline nudges.

Bring your own API keys and run your own instance.

---

## Features

- Detects OAs, HireVue invites, interview invites, and application confirmations from Gmail
- Classifies emails using Gemini Flash 2.0 (free tier, 1500 req/day)
- Daily digest at 09:00 SGT and 24-hour deadline nudges
- `/scan` to manually trigger an inbox poll
- `/tasks`, `/status`, `/upcoming`, `/stats` to view your pipeline
- `/done`, `/add`, `/remove` to manage tasks
- Deduplication by Gmail message ID — safe to scan repeatedly
- Privacy notice + explicit `/confirm` before any Gmail access

---

## Tech stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| Telegram | python-telegram-bot v20 (async) |
| Scheduler | APScheduler 3.x |
| Email | Gmail API via google-auth-oauthlib |
| LLM | Gemini Flash 2.0 |
| Database | SQLite |
| OAuth callback | Flask |

---

## Prerequisites

You need accounts and API keys from four services before running this bot.

### 1. Telegram bot token

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Copy the token — this is your `TELEGRAM_BOT_TOKEN`

### 2. Google OAuth credentials

The bot reads Gmail via OAuth 2.0. Each person who runs the bot needs to authorise it once through a browser.

1. Go to [Google Cloud Console](https://console.cloud.google.com/) and create a new project
2. Enable the **Gmail API**: APIs & Services → Enable APIs → search "Gmail API"
3. Go to APIs & Services → **Credentials** → Create Credentials → **OAuth client ID**
4. Choose **Web application**
5. Under **Authorised redirect URIs**, add your callback URL:
   - Local dev: `http://localhost:5001/oauth/callback`
   - Self-hosted: `http://YOUR_SERVER_IP:5001/oauth/callback`
6. Copy the **Client ID** and **Client Secret**
7. Go to APIs & Services → **OAuth consent screen**:
   - Set User Type to **External**
   - Add your Gmail address as a **Test user** (required while the app is in testing mode)

### 3. Gemini API key

1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Create an API key — this is your `GEMINI_API_KEY`
3. Free tier gives 1500 requests/day, which is sufficient for personal use

---

## Local setup

```bash
git clone https://github.com/shelialia/jobhunttrackingbot.git
cd jobhunttrackingbot

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

Copy the example env file and fill in your keys:

```bash
cp .env.example .env
```

Edit `.env`:

```
TELEGRAM_BOT_TOKEN=your_token_here
GOOGLE_CLIENT_ID=your_client_id_here
GOOGLE_CLIENT_SECRET=your_client_secret_here
OAUTH_REDIRECT_URI=http://localhost:5001/oauth/callback
GEMINI_API_KEY=your_gemini_key_here
DB_PATH=data/jobtracker.db
FLASK_DEBUG=false
```

### Running locally

The bot and the OAuth server are two separate processes. Run each in its own terminal:

**Terminal 1 — OAuth callback server:**
```bash
python -m jobtracker.oauth_server.app
```

**Terminal 2 — Telegram bot:**
```bash
python -m jobtracker.bot.main
```

Then open Telegram and send `/start` to your bot.

> **Note:** Gmail OAuth requires Google to redirect back to your `OAUTH_REDIRECT_URI` after the user authorises access. Locally, this works fine as long as you're authorising from the same machine. If you're running the bot on a remote server without a domain, use [ngrok](https://ngrok.com/) to expose port 5001 and update `OAUTH_REDIRECT_URI` accordingly.

---

## Self-hosting (spare laptop / home server)

Same setup as above. To keep both processes running after you close the terminal:

```bash
# Run both as background processes with logs
nohup python -m jobtracker.oauth_server.app > logs/oauth.log 2>&1 &
nohup python -m jobtracker.bot.main > logs/bot.log 2>&1 &
```

Or use a process manager like [PM2](https://pm2.keymetrics.io/) (works with Python):

```bash
npm install -g pm2
pm2 start "python -m jobtracker.oauth_server.app" --name oauth
pm2 start "python -m jobtracker.bot.main" --name bot
pm2 save
pm2 startup  # auto-restart on reboot
```

---

## Project structure

```
jobtracker/
├── bot/
│   ├── main.py              # Entry point — starts bot + scheduler
│   ├── commands/            # One file per bot command
│   ├── scheduler/
│   │   ├── digest.py        # Daily 09:00 SGT digest
│   │   └── nudge.py         # Hourly 24h deadline nudge
│   ├── gmail/
│   │   ├── auth.py          # OAuth2 URL generation + token refresh
│   │   ├── fetch.py         # Gmail API fetch
│   │   └── parse.py         # Extract subject + body from raw message
│   ├── llm/
│   │   └── classify.py      # Gemini call — classify email, extract fields
│   └── db/
│       ├── schema.py        # CREATE TABLE + migrations
│       ├── users.py         # User CRUD
│       └── tasks.py         # Task CRUD + dedup + linking
└── oauth_server/
    └── app.py               # Flask callback — receives OAuth code from Google
```

---

## How the scan pipeline works

1. Fetch emails from Gmail since `last_scanned_at` filtered by job-related subject keywords
2. Skip any email whose `gmail_id` is already in the database (dedup)
3. Send subject + body to Gemini — get back structured JSON (type, company, role, deadline, link)
4. Skip emails classified as `irrelevant` or with confidence < 0.7 (flagged for manual review)
5. Insert task row; for OA/HireVue/interview, link back to the original application row
6. Update `last_scanned_at`

---

## Contributing

Contributions are welcome. A few things to know before you start:

- The project uses Python 3.11+. Keep it async — `python-telegram-bot` v20 runs on a single asyncio event loop.
- The LLM call in `llm/classify.py` is currently synchronous and blocks the event loop. This is a known issue — if you're fixing multi-user concurrency, the right fix is `generate_content_async()` with a global `asyncio.Semaphore`.
- Deduplication is enforced at the database level via a unique index on `(telegram_id, gmail_id)`. Do not remove or work around this.
- `normalise()` in `db/tasks.py` is used for company/role matching — changes there affect dedup and linking logic.
- There is a hardcoded `last_scanned = datetime(2026, 4, 20)` in `commands/scan.py` left in for testing. Remove this before any production deployment.

To contribute:
1. Fork the repo
2. Create a branch: `git checkout -b fix/your-fix-name`
3. Make your changes and test locally
4. Open a pull request with a clear description of what and why

---

## Known limitations

- LLM calls are synchronous — blocks the event loop under concurrent load (single-user use is fine)
- No per-user notification timezone (hardcoded 09:00 SGT / 01:00 UTC)
- No fuzzy company/role matching — exact normalised match only
- Gmail scope is read-only but all matching emails are sent to Gemini; unrelated emails may occasionally be processed
- Single Gemini API key shared across all users of an instance

---

## License

MIT
