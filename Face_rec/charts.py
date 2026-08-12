"""Shared chart drawing for a single day's mood data.

Backend-agnostic on purpose: the drawing functions take a Figure, so the Tk app
can hand in a TkAgg figure while the web server renders straight to PNG bytes.
"""

import io

from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter
from datetime import datetime

from emotion_engine import EMOTIONS

INK = "#1f2933"
MUTED = "#6b7280"

EMOTION_COLORS = {
    "happiness": "#16a34a",
    "surprise": "#d4a017",
    "neutral": "#9ca3af",
    "contempt": "#7c6fd4",
    "disgust": "#4f86c6",
    "sadness": "#e08a3c",
    "fear": "#c56fc5",
    "anger": "#dc2626",
}


def _clock(v, _pos):
    return f"{int(v) % 24:02d}:{int(round((v % 1) * 60)) % 60:02d}"


def draw_day(fig, summary):
    """Draw the two day charts onto `fig`. Safe to call with summary=None."""
    fig.clear()
    if not summary:
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, "No readings for this day yet",
                ha="center", va="center", fontsize=13, color=MUTED)
        ax.axis("off")
        return

    rows = summary["rows"]
    hours, vals, emos = [], [], []
    for ts, emotion, _conf, valence in rows:
        dt = datetime.fromtimestamp(ts)
        hours.append(dt.hour + dt.minute / 60 + dt.second / 3600)
        vals.append(valence)
        emos.append(emotion)

    ax1 = fig.add_subplot(1, 2, 1)
    ax1.axhspan(0, 1, color="#16a34a", alpha=0.05)
    ax1.axhspan(-1, 0, color="#dc2626", alpha=0.05)
    ax1.axhline(0, color="#9ca3af", lw=0.8)
    ax1.plot(hours, vals, color="#cbd5e1", lw=1, zorder=1)
    ax1.scatter(hours, vals, c=[EMOTION_COLORS.get(e, "#999") for e in emos],
                s=26, zorder=2, edgecolors="white", linewidths=0.5)
    ax1.set_title("Mood through the day", fontsize=11, fontweight="bold", color=INK)
    ax1.xaxis.set_major_formatter(FuncFormatter(_clock))
    ax1.tick_params(axis="x", labelsize=8)
    ax1.set_xlabel("time of day", fontsize=9, color=MUTED)
    ax1.set_ylabel("negative      neutral      positive", fontsize=9, color=MUTED)
    ax1.set_ylim(-1.05, 1.05)
    ax1.set_yticks([])
    ax1.set_facecolor("white")
    for sp in ("top", "right"):
        ax1.spines[sp].set_visible(False)

    ax2 = fig.add_subplot(1, 2, 2)
    counts = summary["counts"]
    present = [(e, counts[e]) for e in EMOTIONS if counts.get(e, 0) > 0]
    present.sort(key=lambda x: x[1])
    total = sum(c for _, c in present) or 1
    names = [e.capitalize() for e, _ in present]
    pcts = [100 * c / total for _, c in present]
    ax2.barh(names, pcts, color=[EMOTION_COLORS.get(e, "#999") for e, _ in present])
    for i, p in enumerate(pcts):
        ax2.text(p + 1, i, f"{p:.0f}%", va="center", fontsize=9, color=MUTED)
    ax2.set_title("Share of the day", fontsize=11, fontweight="bold", color=INK)
    ax2.set_xlim(0, max(pcts) * 1.2 if pcts else 1)
    ax2.set_xticks([])
    ax2.set_facecolor("white")
    for sp in ("top", "right", "bottom"):
        ax2.spines[sp].set_visible(False)

    fig.tight_layout(pad=1.6)


def render_png(summary, width=9.0, height=4.0, dpi=100, facecolor="white"):
    """Render a day's charts to PNG bytes (no GUI backend needed)."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    fig = Figure(figsize=(width, height), dpi=dpi, facecolor=facecolor)
    FigureCanvasAgg(fig)
    draw_day(fig, summary)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=facecolor)
    return buf.getvalue()
