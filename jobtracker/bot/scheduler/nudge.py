from telegram import Bot
from ..db import tasks as tasks_db


async def send_deadline_nudges(bot: Bot) -> None:
    due_soon = tasks_db.get_all_tasks_due_soon()

    for task in due_soon:
        telegram_id = task["telegram_id"]
        company = task["company"] or "Unknown"
        task_type = task["type"].upper()
        deadline = task["deadline"][:16].replace("T", " ") if task["deadline"] else "soon"

        message = (
            f"Deadline reminder: *{company}* — {task_type}\n"
            f"Due: {deadline} UTC\n\n"
            "Use /done to mark it complete."
        )
        if task["link"]:
            message += f"\nLink: {task['link']}"

        try:
            await bot.send_message(
                chat_id=telegram_id,
                text=message,
                parse_mode="Markdown",
            )
            tasks_db.mark_nudged(task["id"])
        except Exception:
            pass
