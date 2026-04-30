import os
import logging
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .db.schema import init_db
from .commands.start import start
from .commands.connect import connect
from .commands.status import status
from .commands.upcoming import upcoming
from .commands.stats import stats
from .commands.scan import scan
from .commands.done import done
from .commands.add import add
from .commands.remove import remove
from .commands.cycles import list_cycles, new_cycle
from .commands.help import help_cmd
from .scheduler.digest import send_daily_digest
from .scheduler.nudge import send_deadline_nudges

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    init_db()

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("connect", connect))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("upcoming", upcoming))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("scan", scan))
    app.add_handler(CommandHandler("done", done))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("remove", remove))
    app.add_handler(CommandHandler("cycles", list_cycles))
    app.add_handler(CommandHandler("newcycle", new_cycle))
    app.add_handler(CommandHandler("help", help_cmd))

    scheduler = AsyncIOScheduler()
    bot = app.bot

    scheduler.add_job(
        send_daily_digest,
        CronTrigger(hour=1, minute=0),
        args=[bot],
        id="daily_digest",
        name="Daily digest",
        replace_existing=True,
    )
    scheduler.add_job(
        send_deadline_nudges,
        IntervalTrigger(hours=1),
        args=[bot],
        id="hourly_nudge",
        name="Hourly deadline nudge",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("Scheduler started")

    logger.info("Bot polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
