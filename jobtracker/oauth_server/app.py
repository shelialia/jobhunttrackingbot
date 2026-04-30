import os
import sys
import requests
from flask import Flask, request, redirect
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

load_dotenv()

from jobtracker.bot.gmail.auth import exchange_code_for_token
from jobtracker.bot.db.users import update_gmail_token, get_user

app = Flask(__name__)


def _send_telegram(telegram_id: int, text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": telegram_id, "text": text, "parse_mode": "Markdown"},
            timeout=5,
        )
    except Exception:
        pass


@app.route("/oauth/callback")
def oauth_callback():
    code = request.args.get("code")
    state = request.args.get("state")  # telegram_id

    if not code or not state:
        return "Missing code or state.", 400

    try:
        telegram_id = int(state)
    except ValueError:
        return "Invalid state.", 400

    user = get_user(telegram_id)
    if not user:
        return "User not found. Please send /start to the bot first.", 404

    try:
        token_json = exchange_code_for_token(code)
    except Exception as e:
        return f"OAuth error: {e}", 500

    update_gmail_token(telegram_id, token_json)

    _send_telegram(
        telegram_id,
        "✅ *Gmail connected successfully!*\n\n"
        "Use /scan to scan the last month of your inbox.\n"
        "_This may take a few minutes — I'll notify you when it's done!_",
    )

    return (
        "<h2>Gmail connected!</h2>"
        "<p>You can close this tab and return to Telegram. "
        "Use <b>/scan</b> to trigger your first inbox scan.</p>"
    )


if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=5001, debug=debug, use_reloader=debug)
