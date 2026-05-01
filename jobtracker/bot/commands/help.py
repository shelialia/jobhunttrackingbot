from telegram import Update
from telegram.ext import ContextTypes

HELP_TEXT = """
🤖 <b>CronJobBot - Commands</b>

📋 <b>Tracking</b>
/tasks — Assessments & interviews to complete
/applied — All applications submitted
/stats — Job hunt stats for your active cycle
/sankey — Export your funnel Sankey diagram
/upcoming — Tasks due in the next 7 days
/timeline &lt;app_number&gt; — Show full progress for one application

✅ <b>Actions</b>
/done &lt;task_number&gt; — Mark a task as done
/offer &lt;app_number&gt; — Mark an application as an offer
/reject &lt;app_number&gt; — Mark an application as rejected
/remove &lt;task_number or app_number&gt; — Delete a task or application

✏️ <b>Management</b>
/scan — Scan Gmail for new tasks
/add &lt;company&gt; [date] [type] — Add a task manually
/connect — Connect your Gmail account

🔄 <b>Cycles</b>
/cycles — View all your cycles
/newcycle — Start a new cycle
/switchcycle — Switch to a different cycle

/help — Show this message
""".strip()


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT, parse_mode="HTML")
