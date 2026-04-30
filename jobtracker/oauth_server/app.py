import os
import sys
from flask import Flask, request, redirect
from dotenv import load_dotenv

# Allow imports from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

load_dotenv()

from jobtracker.bot.gmail.auth import exchange_code_for_token
from jobtracker.bot.db.users import update_gmail_token, get_user

app = Flask(__name__)


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

    return (
        "<h2>Gmail connected!</h2>"
        "<p>You can close this tab and return to Telegram. "
        "Use /scan to trigger your first inbox scan.</p>"
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
