from telegram import Update
from telegram.ext import ContextTypes
from ..db import cycles as cycles_db


async def handle_cycle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    data = query.data
    telegram_id = update.effective_user.id

    if data == "cycle_action:new":
        context.user_data["awaiting_cycle_name"] = "newcycle"
        await query.message.reply_text(
            "What would you like to name your new cycle?\n"
            '_(e.g. "Summer 2025", "Full Time 2026")_',
            parse_mode="Markdown",
        )
        return

    if data.startswith("switch_cycle:"):
        cycle_id = int(data.split(":")[1])
        all_cycles = cycles_db.get_all_cycles(telegram_id)
        target = next((c for c in all_cycles if c["id"] == cycle_id), None)
        if not target:
            await query.edit_message_text("Cycle not found.")
            return
        cycles_db.switch_to_cycle(telegram_id, cycle_id)
        await query.edit_message_text(
            f'✅ Switched to *"{target["name"]}"*.\n\nAll new scans will use this cycle.',
            parse_mode="Markdown",
        )
