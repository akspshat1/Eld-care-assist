"""Chart drawing for a day of voice mood readings.

Uses a Japanese-capable font when one is installed, so the emotion names
render as 喜び / 悲しみ rather than tofu boxes; falls back to English labels
if no CJK font is found.
"""

import io
from datetime import datetime

from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter
from matplotlib import font_manager

from voice_engine import EMOTIONS, COLORS, label_ja, label_en

INK = "#1f2933"
MUTED = "#6b7280"

_CJK_CANDIDATES = ["Yu Gothic", "Meiryo", "MS Gothic", "Noto Sans CJK JP",
                   "BIZ UDGothic", "Hiragino Sans", "IPAexGothic"]


def _cjk_font():
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in _CJK_CANDIDATES:
        if name in available:
            return name
    return None


CJK_FONT = _cjk_font()

TEXT = {
    "en": {"timeline": "Mood through the day", "share": "Share of the day",
           "time": "time of day", "empty": "No readings for this day yet"},
    "ja": {"timeline": "一日の気分の変化", "share": "感情の割合",
           "time": "時刻", "empty": "この日の記録はまだありません"},
}


def _resolve(lang):
    """Japanese only if we can actually render it; otherwise fall back."""
    return "ja" if (lang == "ja" and CJK_FONT) else "en"


def _label(code, lang):
    return label_ja(code) if lang == "ja" else label_en(code)


def _apply_font(ax, lang):
    if lang == "ja" and CJK_FONT:
        for item in ([ax.title, ax.xaxis.label, ax.yaxis.label]
                     + ax.get_xticklabels() + ax.get_yticklabels()):
            item.set_fontname(CJK_FONT)


def _clock(v, _pos):
    return f"{int(v) % 24:02d}:{int(round((v % 1) * 60)) % 60:02d}"


def draw_day(fig, summary, lang="en"):
    lang = _resolve(lang)
    t = TEXT[lang]
    fig.clear()
    if not summary:
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, t["empty"], ha="center", va="center", fontsize=13,
                color=MUTED, fontname=CJK_FONT if lang == "ja" else None)
        ax.axis("off")
        return

    rows = summary["rows"]
    hours, vals, emos = [], [], []
    for ts, emotion, _conf, valence, _src in rows:
        dt = datetime.fromtimestamp(ts)
        hours.append(dt.hour + dt.minute / 60 + dt.second / 3600)
        vals.append(valence)
        emos.append(emotion)

    ax1 = fig.add_subplot(1, 2, 1)
    ax1.axhspan(0, 1, color="#16a34a", alpha=0.05)
    ax1.axhspan(-1, 0, color="#dc2626", alpha=0.05)
    ax1.axhline(0, color="#9ca3af", lw=0.8)
    ax1.plot(hours, vals, color="#cbd5e1", lw=1, zorder=1)
    ax1.scatter(hours, vals, c=[COLORS.get(e, "#999") for e in emos],
                s=46, zorder=2, edgecolors="white", linewidths=0.6)
    ax1.set_title(t["timeline"], fontsize=11, fontweight="bold", color=INK)
    ax1.xaxis.set_major_formatter(FuncFormatter(_clock))
    ax1.tick_params(axis="x", labelsize=8)
    ax1.set_xlabel(t["time"], fontsize=9, color=MUTED)
    ax1.set_ylim(-1.05, 1.05)
    ax1.set_yticks([])
    ax1.set_facecolor("white")
    for sp in ("top", "right"):
        ax1.spines[sp].set_visible(False)
    _apply_font(ax1, lang)

    ax2 = fig.add_subplot(1, 2, 2)
    counts = summary["counts"]
    present = [(e, counts[e]) for e in EMOTIONS if counts.get(e, 0) > 0]
    present.sort(key=lambda x: x[1])
    total = sum(c for _, c in present) or 1
    names = [_label(e, lang) for e, _ in present]
    pcts = [100 * c / total for _, c in present]
    ax2.barh(names, pcts, color=[COLORS.get(e, "#999") for e, _ in present])
    for i, p in enumerate(pcts):
        ax2.text(p + 1, i, f"{p:.0f}%", va="center", fontsize=9, color=MUTED)
    ax2.set_title(t["share"], fontsize=11, fontweight="bold", color=INK)
    ax2.set_xlim(0, max(pcts) * 1.2 if pcts else 1)
    ax2.set_xticks([])
    ax2.set_facecolor("white")
    for sp in ("top", "right", "bottom"):
        ax2.spines[sp].set_visible(False)
    _apply_font(ax2, lang)

    fig.tight_layout(pad=1.6)


def render_png(summary, lang="en", width=9.0, height=4.0, dpi=100,
               facecolor="white"):
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    fig = Figure(figsize=(width, height), dpi=dpi, facecolor=facecolor)
    FigureCanvasAgg(fig)
    draw_day(fig, summary, lang)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=facecolor)
    return buf.getvalue()
