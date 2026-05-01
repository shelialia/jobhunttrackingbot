import os
import tempfile

from telegram import Update
from telegram.ext import ContextTypes

from ..db import cycles as cycles_db, tasks as tasks_db, users


_NODE_ORDER = ["application", "oa", "hirevue", "interview", "offer", "rejection", "ghosted"]
_NODE_COLORS = {
    "application": "#3b82f6",
    "oa": "#f97316",
    "hirevue": "#8b5cf6",
    "interview": "#14b8a6",
    "offer": "#22c55e",
    "rejection": "#ef4444",
    "ghosted": "#808080",
}
_NODE_LABELS = {
    "application": "Application",
    "oa": "OA",
    "hirevue": "HireVue",
    "interview": "Interview",
    "offer": "Offer",
    "rejection": "Rejection",
    "ghosted": "Ghosted",
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
    try:
        import kaleido  # noqa: F401
    except ImportError:
        await update.message.reply_text("Kaleido is not installed. Add it to the environment before using /sankey.")
        return

    edges = tasks_db.get_sankey_edges(telegram_id, cycle["id"])

    node_indices = {label: idx for idx, label in enumerate(_NODE_ORDER)}
    source_indices = [node_indices[source] for source, _, _ in edges]
    target_indices = [node_indices[target] for _, target, _ in edges]
    flow_values = [flow for _, _, flow in edges]
    outgoing_counts = {label: 0 for label in _NODE_ORDER}
    incoming_counts = {label: 0 for label in _NODE_ORDER}
    for source, target, flow in edges:
        outgoing_counts[source] += flow
        incoming_counts[target] += flow

    node_labels = []
    for label in _NODE_ORDER:
        count = outgoing_counts[label] if outgoing_counts[label] else incoming_counts[label]
        node_labels.append(f"{_NODE_LABELS[label]} ({count})")

    fig = go.Figure(
        go.Sankey(
            domain=dict(x=[0.0, 1.0], y=[0.0, 1.0]),
            node=dict(
                label=node_labels,
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
        title=dict(
            text=f"<b>Job Search Funnel - {cycle['name']}</b>",
            x=0.5,
            xanchor="center",
            font=dict(size=28, color="#111827"),
        ),
        font_size=12,
        width=1400,
        height=900,
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=40, r=40, t=80, b=40),
    )

    temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    try:
        temp_file.close()
        fig.write_image(temp_file.name, format="png", scale=2)
        with open(temp_file.name, "rb") as handle:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=handle,
                caption=f"📊 <b>Job Search Funnel - {cycle['name']}</b>",
                parse_mode="HTML",
            )
    finally:
        if not temp_file.closed:
            temp_file.close()
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name)
