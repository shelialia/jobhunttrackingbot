# Contributing

Thanks for considering a contribution to Job Hunt Tracker Bot.

This project is a self-hosted, BYOK Telegram bot for tracking job applications from Gmail. Contributions are welcome, especially fixes that improve parsing, linking, privacy, setup, and reliability.

## Before You Start

Please keep these project goals in mind:

- The bot should stay self-hosted friendly.
- Users should keep control of their own Gmail tokens, bot credentials, model key, and database.
- Chain correctness matters more than cosmetic refactors.
- Follow-up events should attach to the right application chain.
- Interview invite, scheduling, and confirmation emails should update one interview round when they refer to the same round.

## Ways To Contribute

Useful contributions include:

- Bug reports with example email shapes, with private details removed.
- Parser and classification improvements.
- Better setup and hosting documentation.
- Regression checks for scan, timeline, stats, and Sankey behavior.
- Safer correction flows for false positives.
- Small reliability fixes around Gmail, Telegram, SQLite, or model responses.

## Local Setup

Follow the setup instructions in `README.md`.

At minimum, you will need:

- Python 3.11+
- A Telegram bot token
- Google OAuth credentials with Gmail API enabled
- A Gemini API key

Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create your local `.env`:

```bash
cp .env.example .env
```

Then run the OAuth server and bot in separate terminals:

```bash
python -m jobtracker.oauth_server.app
```

```bash
python -m jobtracker.bot.main
```

## Basic Checks

Before opening a pull request, run:

```bash
python -m compileall jobtracker
```

If your change affects scanning, linking, classification, stats, or diagrams, manually re-check the affected Telegram commands.

Useful regression checks:

- `/scan`
- `/tasks`
- `/applied`
- `/timeline`
- `/stats`
- `/sankey`
- `/upcoming`

## Pull Requests

For PRs, please include:

- What problem the change fixes.
- What behavior changed.
- How you tested it.
- Any before/after chain shape if the change affects task linking.

For linking-related changes, describe whether the expected chain is something like:

```text
application -> oa -> interview -> offer
```

or:

```text
ghost application -> interview -> rejection
```

## Privacy

Do not include real Gmail messages, tokens, recruiter names, or private application data in issues, pull requests, screenshots, or test fixtures.

If you need to share an example, redact or rewrite it into a synthetic example first.
