from telegram import Update
from telegram.ext import ContextTypes

HELP_TEXT = """
*Job Hunt Tracker — Commands*

/start — Onboard and create your first cycle
/connect — Connect your Gmail account
/status — All pending tasks sorted by urgency
/upcoming — Tasks due in the next 7 days
/stats — Current cycle statistics
/stats <label> — Stats for a named past cycle
/scan — Manually trigger a Gmail scan
/done <company> — Mark a task as done
/add <company> [date] [type] — Add a task manually
/remove <company> — Remove a wrongly detected task
/cycles — List all your cycles
/newcycle <label> — Close current cycle and start a new one
/help — Show this message
""".strip()


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")
