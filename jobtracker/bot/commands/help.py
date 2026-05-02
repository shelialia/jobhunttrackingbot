from telegram import Update
from telegram.ext import ContextTypes
from ..message_utils import reply_chunked_lines

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
/done &lt;assessment_index&gt; — Mark an assessment as done
/done i&lt;interview_index&gt; — Mark an interview as done
/offer &lt;app_number&gt; — Mark an application as an offer
/reject &lt;app_number&gt; — Mark an application as rejected
/remove &lt;app_index&gt; — Delete an application after /applied
/remove &lt;assessment_index&gt; — Delete an assessment after /tasks
/remove i&lt;interview_index&gt; — Delete an interview after /tasks

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
    await reply_chunked_lines(update.message, HELP_TEXT.split("\n"), parse_mode="HTML")
