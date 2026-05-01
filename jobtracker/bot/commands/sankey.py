import os
import tempfile

from telegram import Update
from telegram.ext import ContextTypes

from ..db import cycles as cycles_db, tasks as tasks_db, users


_NODE_ORDER = ["application", "oa", "hirevue", "interview", "offer", "rejection"]
_NODE_COLORS = {
    "application": "#3b82f6",
    "oa": "#f97316",
    "hirevue": "#8b5cf6",
    "interview": "#14b8a6",
    "offer": "#22c55e",
    "rejection": "#ef4444",
}


async def sankey(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    if not users.get_user(telegram_id):
        await update.message.reply_text("Please run /start first.")
        return

    cycle = cycles_db.get_active_cycle(telegram_id)
    if not cycle:
        await update.message.reply_text(
            "No active cycle. Use /newcycle to create one, or /cycles to switch to an existing one."
        )
        return

    try:
        import plotly.graph_objects as go
    except ImportError:
        await update.message.reply_text("Plotly is not installed. Add it to the environment before using /sankey.")
        return

    edges = tasks_db.get_sankey_edges(telegram_id, cycle["id"])
    breakdown = tasks_db.get_interview_breakdown(telegram_id, cycle["id"])

    node_indices = {label: idx for idx, label in enumerate(_NODE_ORDER)}
    source_indices = [node_indices[source] for source, _, _ in edges]
    target_indices = [node_indices[target] for _, target, _ in edges]
    flow_values = [flow for _, _, flow in edges]

    fig = go.Figure(
        go.Sankey(
            node=dict(
                label=_NODE_ORDER,
                color=[_NODE_COLORS[label] for label in _NODE_ORDER],
                pad=15,
                thickness=20,
            ),
            link=dict(
                source=source_indices,
                target=target_indices,
                value=flow_values,
            ),
        )
    )
    fig.update_layout(
        title=f"Job Search Funnel - {cycle['name']}",
        font_size=12,
    )

    bucket_rows = "".join(
        f"<tr><td>{label}</td><td>{count}</td></tr>"
        for label, count in breakdown["buckets"].items()
    )
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Job Search Funnel - {cycle['name']}</title>
</head>
<body>
  {fig.to_html(full_html=False, include_plotlyjs='cdn')}
  <h2>Interview Depth</h2>
  <table border="1" cellpadding="6" cellspacing="0">
    <thead><tr><th>Bucket</th><th>Count</th></tr></thead>
    <tbody>{bucket_rows}</tbody>
  </table>
</body>
</html>
"""

    temp_file = tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8")
    try:
        temp_file.write(html)
        temp_file.close()
        with open(temp_file.name, "rb") as handle:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=handle,
                filename="sankey.html",
            )
    finally:
        if not temp_file.closed:
            temp_file.close()
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name)
