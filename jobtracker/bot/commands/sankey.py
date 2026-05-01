import os
import tempfile

from telegram import Update
from telegram.ext import ContextTypes

from ..db import cycles as cycles_db, tasks as tasks_db, users


_NODE_COLORS = {
    "application": "#3b82f6",
    "oa": "#f97316",
    "hirevue": "#8b5cf6",
    "offer": "#22c55e",
    "rejection": "#ef4444",
    "ghosted": "#808080",
    "pending": "#F0A500",
}
_INTERVIEW_COLOR = "#14b8a6"


def _ordinal(n: int) -> str:
    if 10 <= (n % 100) <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _node_label(node: str) -> str:
    if node.startswith("interview_"):
        try:
            round_number = int(node.split("_", 1)[1])
        except (IndexError, ValueError):
            return "Interview"
        return f"{_ordinal(round_number)} Interview"

    labels = {
        "application": "Application",
        "oa": "OA",
        "hirevue": "HireVue",
        "offer": "Offer",
        "rejection": "Rejection",
        "ghosted": "Ghosted",
        "pending": "Pending",
    }
    return labels.get(node, node.title())


def _node_color(node: str) -> str:
    if node.startswith("interview_"):
        return _INTERVIEW_COLOR
    return _NODE_COLORS[node]


def _node_sort_key(node: str) -> tuple[int, int]:
    order = {
        "application": 0,
        "oa": 1,
        "hirevue": 2,
        "offer": 100,
        "rejection": 101,
        "ghosted": 102,
        "pending": 103,
    }
    if node.startswith("interview_"):
        try:
            round_number = int(node.split("_", 1)[1])
        except (IndexError, ValueError):
            round_number = 1
        return (3 + round_number, round_number)
    return (order.get(node, 999), 0)


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
    nodes = sorted({node for edge in edges for node in edge[:2]}, key=_node_sort_key)

    node_indices = {label: idx for idx, label in enumerate(nodes)}
    source_indices = [node_indices[source] for source, _, _ in edges]
    target_indices = [node_indices[target] for _, target, _ in edges]
    flow_values = [flow for _, _, flow in edges]
    outgoing_counts = {label: 0 for label in nodes}
    incoming_counts = {label: 0 for label in nodes}
    for source, target, flow in edges:
        outgoing_counts[source] += flow
        incoming_counts[target] += flow

    node_labels = []
    for label in nodes:
        count = outgoing_counts[label] if outgoing_counts[label] else incoming_counts[label]
        node_labels.append(f"{_node_label(label)} ({count})")

    fig = go.Figure(
        go.Sankey(
            domain=dict(x=[0.0, 1.0], y=[0.0, 1.0]),
            node=dict(
                label=node_labels,
                color=[_node_color(label) for label in nodes],
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
