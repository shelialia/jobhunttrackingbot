from telegram import Update
from telegram.ext import ContextTypes

HELP_TEXT = """
🤖 *Job Hunt Tracker — Commands*

📋 *Tracking*
/tasks — Assessments & interviews to complete
/applied — All applications submitted
/stats — Your job hunt stats
/upcoming — Tasks due in the next 7 days

✅ *Actions*
/done <task_number> — Mark a task as done
/offer <app_number> — Mark an application as an offer
/reject <app_number> — Mark an application as rejected
/remove <task_number or app_number> — Delete a task or application
/confirm — Confirm a pending action

✏️ *Management*
/scan — Scan Gmail for new tasks
/add <company> [date] [type] — Add a task manually
/connect — Connect your Gmail account
/help — Show this message
""".strip()


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")
