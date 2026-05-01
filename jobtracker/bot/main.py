import os
import logging
from dotenv import load_dotenv
from telegram import BotCommand
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .db.schema import init_db
from .commands.start import start
from .commands.connect import connect
from .commands.upcoming import upcoming
from .commands.scan import scan
from .commands.tasks import tasks_cmd
from .commands.applied import applied
from .commands.stats import stats
from .commands.sankey import sankey
from .commands.timeline import timeline
from .commands.done import done
from .commands.offer import offer
from .commands.reject import reject
from .commands.confirm import confirm
from .commands.add import add
from .commands.remove import remove
from .commands.help import help_cmd
from .commands.cycles import cycles_cmd
from .commands.newcycle import newcycle
from .commands.switchcycle import switchcycle
from .commands.cycle_callbacks import handle_cycle_callback
from .commands.text_input import handle_text_message
from .scheduler.digest import send_daily_digest

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_COMMANDS = [
    BotCommand("start", "Set up your account"),
    BotCommand("tasks", "Assessments and interviews to complete"),
    BotCommand("applied", "All applications submitted"),
    BotCommand("upcoming", "Tasks due in the next 7 days"),
    BotCommand("stats", "Job hunt stats for your active cycle"),
    BotCommand("sankey", "Export your funnel Sankey diagram"),
    BotCommand("scan", "Manually scan Gmail now"),
    BotCommand("timeline", "Show the full progress for one application"),
    BotCommand("done", "Mark a task as done"),
    BotCommand("offer", "Mark an application as an offer"),
    BotCommand("reject", "Mark an application as rejected"),
    BotCommand("remove", "Delete a task"),
    BotCommand("add", "Manually add a task"),
    BotCommand("connect", "Connect your Gmail account"),
    BotCommand("cycles", "View all your cycles"),
    BotCommand("newcycle", "Start a new cycle"),
    BotCommand("switchcycle", "Switch to a different cycle"),
    BotCommand("help", "List all commands"),
]


async def _post_init(application: Application) -> None:
    await application.bot.set_my_commands(_COMMANDS)
    logger.info("Bot commands registered")


def main() -> None:
    init_db()

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).post_init(_post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("connect", connect))
    app.add_handler(CommandHandler("scan", scan))
    app.add_handler(CommandHandler("tasks", tasks_cmd))
    app.add_handler(CommandHandler("applied", applied))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("sankey", sankey))
    app.add_handler(CommandHandler("upcoming", upcoming))
    app.add_handler(CommandHandler("timeline", timeline))
    app.add_handler(CommandHandler("done", done))
    app.add_handler(CommandHandler("offer", offer))
    app.add_handler(CommandHandler("reject", reject))
    app.add_handler(CommandHandler("confirm", confirm))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("remove", remove))
    app.add_handler(CommandHandler("cycles", cycles_cmd))
    app.add_handler(CommandHandler("newcycle", newcycle))
    app.add_handler(CommandHandler("switchcycle", switchcycle))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(handle_cycle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        send_daily_digest,
        CronTrigger(hour=1, minute=0),
        args=[app.bot],
        id="daily_digest",
        name="Daily digest",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started")

    logger.info("Bot polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
