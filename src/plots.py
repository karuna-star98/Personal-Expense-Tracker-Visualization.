"""Static charts (Matplotlib + Seaborn) saved as PNG for README, reports and GitHub proof."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")                       # headless: no display needed
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.ticker import FuncFormatter

from . import analyze, config
from .config import CATEGORY_COLORS, PAYMENT_COLORS, inr

INK, MUTED, GRID, ACCENT, GOOD, BAD = "#0F172A", "#64748B", "#E2E8F0", "#4F46E5", "#10B981", "#EF4444"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "axes.edgecolor": GRID, "axes.labelcolor": MUTED, "xtick.color": MUTED,
    "ytick.color": MUTED, "axes.titleweight": "bold", "axes.titlesize": 12, "axes.titlecolor": INK,
    "axes.titlelocation": "left", "figure.dpi": 100, "savefig.dpi": 160, "axes.spines.top": False,
    "axes.spines.right": False,
})

_short = FuncFormatter(lambda v, _: f"{config.CURRENCY_SYMBOL}{v/1000:,.0f}k" if abs(v) >= 1000 else f"{config.CURRENCY_SYMBOL}{v:,.0f}")


def _scope(month: str | None) -> str:
    return analyze.month_label(month) if month else "All time"


def _fig(ax, size):
    if ax is not None:
        return ax.figure, ax
    fig, ax = plt.subplots(figsize=size)
    return fig, ax


def _empty(ax, text="No data for this period"):
    ax.text(0.5, 0.5, text, ha="center", va="center", color=MUTED, transform=ax.transAxes)
    ax.set_axis_off()


# ----------------------------------------------------------------------------
# Individual charts - each accepts an optional Axes so it can be reused in the dashboard image
# ----------------------------------------------------------------------------
def plot_category_bar(df, month=None, ax=None):
    """Category-wise spending (horizontal bar, sorted, labelled with amount and share)."""
    fig, ax = _fig(ax, (9, 5.2))
    cs = analyze.category_summary(df, month)
    ax.set_title(f"Spending by category - {_scope(month)}")
    if cs.empty:
        _empty(ax); return fig
    cs = cs.iloc[::-1]
    colors = [CATEGORY_COLORS.get(c, "#94A3B8") for c in cs["category"]]
    bars = ax.barh(cs["category"], cs["spend"], color=colors, height=0.68)
    for b, (_, r) in zip(bars, cs.iterrows()):
        ax.text(b.get_width() + cs["spend"].max() * 0.012, b.get_y() + b.get_height() / 2,
                f"{inr(r['spend'])}  ({r['share_pct']:.0f}%)", va="center", fontsize=8.5, color=INK)
    ax.set_xlim(0, cs["spend"].max() * 1.28)
    ax.xaxis.set_major_formatter(_short)
    ax.grid(axis="x", color=GRID); ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    return fig


def plot_monthly_trend(df, ax=None, highlight: str | None = None):
    """Monthly spending line (with income + average line) over the whole history."""
    fig, ax = _fig(ax, (10, 4.8))
    ms = analyze.monthly_summary(df)
    ms = ms[ms["month"].isin(analyze.complete_months(df))]          # partial month would look like a crash
    ax.set_title("Monthly spending trend")
    if ms.empty:
        _empty(ax); return fig
    x = np.arange(len(ms)); labels = [analyze.month_label(m).replace(" 20", " '") for m in ms["month"]]
    ax.fill_between(x, ms["spend"], color=ACCENT, alpha=0.10)
    ax.plot(x, ms["spend"], color=ACCENT, marker="o", lw=2.4, label="Spending")
    ax.plot(x, ms["income"], color=GOOD, ls="--", lw=1.6, marker="s", ms=3.5, label="Income")
    avg = ms["spend"].mean()
    ax.axhline(avg, color=MUTED, lw=1, ls=":")
    ax.text(-0.3, avg, f"avg {inr(avg)}", va="bottom", ha="left", fontsize=8, color=MUTED)
    hi = ms["spend"].idxmax(); pos = list(ms.index).index(hi)
    ax.annotate(f"Peak {inr(ms.loc[hi, 'spend'])}", (pos, ms.loc[hi, "spend"]), textcoords="offset points",
                xytext=(0, 22), ha="center", fontsize=8.5, color=BAD, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.25", fc="white", ec=BAD, lw=0.8), arrowprops=dict(arrowstyle="-", color=BAD, lw=0.8))
    if highlight in list(ms["month"]):
        ax.axvspan(list(ms["month"]).index(highlight) - .4, list(ms["month"]).index(highlight) + .4, color=ACCENT, alpha=.08)
    ax.set_xticks(x); ax.set_xticklabels(labels, rotation=35, ha="right")
    ax.yaxis.set_major_formatter(_short); ax.grid(axis="y", color=GRID); ax.set_axisbelow(True)
    ax.set_ylim(0, max(ms["spend"].max(), ms["income"].max()) * 1.25)
    ax.legend(frameon=False, loc="upper left", ncol=2, fontsize=8.5)
    return fig


def plot_payment_donut(df, month=None, ax=None):
    """Payment-method split as a donut chart."""
    fig, ax = _fig(ax, (6, 5.2))
    ps = analyze.payment_summary(df, month)
    ax.set_title(f"Payment methods - {_scope(month)}")
    if ps.empty:
        _empty(ax); return fig
    colors = [PAYMENT_COLORS.get(m, "#94A3B8") for m in ps["payment_method"]]
    wedges, _ = ax.pie(ps["spend"], colors=colors, startangle=90, counterclock=False,
                       wedgeprops={"width": 0.42, "edgecolor": "white", "linewidth": 2})
    ax.text(0, 0.06, inr(ps["spend"].sum()), ha="center", va="center", fontsize=13, fontweight="bold", color=INK)
    ax.text(0, -0.14, "total spend", ha="center", va="center", fontsize=8.5, color=MUTED)
    ax.legend(wedges, [f"{m}  {s:.0f}%" for m, s in zip(ps["payment_method"], ps["share_pct"])],
              loc="center left", bbox_to_anchor=(0.98, 0.5), frameon=False, fontsize=8.5)
    ax.set_aspect("equal")
    return fig


def plot_category_donut(df, month=None, ax=None):
    fig, ax = _fig(ax, (6, 5.2))
    cs = analyze.category_summary(df, month)
    ax.set_title(f"Category split - {_scope(month)}")
    if cs.empty:
        _empty(ax); return fig
    top = cs.head(7)
    other = cs["spend"].iloc[7:].sum()
    vals = list(top["spend"]) + ([other] if other > 0 else [])
    names = list(top["category"]) + (["Other"] if other > 0 else [])
    colors = [CATEGORY_COLORS.get(n, "#CBD5E1") for n in names]
    wedges, _ = ax.pie(vals, colors=colors, startangle=90, counterclock=False,
                       wedgeprops={"width": 0.42, "edgecolor": "white", "linewidth": 2})
    ax.legend(wedges, [f"{n}  {v / sum(vals) * 100:.0f}%" for n, v in zip(names, vals)], loc="center left",
              bbox_to_anchor=(0.98, 0.5), frameon=False, fontsize=8.5)
    ax.set_aspect("equal")
    return fig


def plot_daily_trend(df, month=None, ax=None):
    """Daily spend bars (weekends tinted) with a 7-day moving average."""
    fig, ax = _fig(ax, (10, 4.6))
    d = analyze.daily_spend(df, month)
    ax.set_title(f"Daily spending - {_scope(month)}")
    if d.empty:
        _empty(ax); return fig
    colors = [("#C7D2FE" if x.dayofweek >= 5 else "#DDE3EE") for x in d["date"]]
    ax.bar(d["date"], d["spend"], color=colors, width=0.8)
    ax.plot(d["date"], d["ma7"], color=ACCENT, lw=2.4, label="7-day average")
    peak = d.loc[d["spend"].idxmax()]
    ax.annotate(f"{inr(peak['spend'])}\n{peak['date']:%d %b}", (peak["date"], peak["spend"]), textcoords="offset points",
                xytext=(0, 6), ha="center", fontsize=8, color=BAD)
    ax.yaxis.set_major_formatter(_short); ax.grid(axis="y", color=GRID); ax.set_axisbelow(True)
    ax.set_ylim(0, d["spend"].max() * 1.25)
    if month:
        ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%d"))
        ax.set_xlabel("Day of month  (shaded = weekend)")
    else:
        ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b '%y"))
    ax.legend(frameon=False, loc="upper right", fontsize=8.5)
    return fig


def plot_weekday_heatmap(df, month=None, ax=None):
    """Category x weekday heatmap - when and where does the money go?"""
    fig, ax = _fig(ax, (9, 5))
    pv = analyze.weekday_category_matrix(df, month)
    ax.set_title(f"Spend by weekday and category - {_scope(month)}")
    if pv.empty:
        _empty(ax); return fig
    labels = pv.map(lambda v: f"{v / 1000:.1f}k" if v >= 1000 else (f"{v:.0f}" if v else ""))
    sns.heatmap(pv, ax=ax, cmap=sns.light_palette(ACCENT, as_cmap=True), annot=labels, fmt="", linewidths=1.5,
                linecolor="white", cbar=False, annot_kws={"fontsize": 7.5})
    ax.set_xlabel(""); ax.set_ylabel(""); ax.tick_params(length=0)
    return fig


def plot_budget_vs_actual(status: pd.DataFrame, month: str, ax=None):
    """Budget progress bars: grey = limit, colour = actual (red when over)."""
    fig, ax = _fig(ax, (9, 5))
    ax.set_title(f"Budget vs actual - {_scope(month)}")
    if status is None or status.empty:
        _empty(ax, "No budgets set for this month"); return fig
    s = status.sort_values("utilization_pct").reset_index(drop=True)
    y = np.arange(len(s))
    ax.barh(y, s["limit"], color="#EEF2F7", height=0.7)
    cols = [BAD if st == "Over budget" else "#F59E0B" if st == "Warning" else GOOD for st in s["status"]]
    ax.barh(y, s["spend"], color=cols, height=0.42)
    xmax = max(s["limit"].max(), s["spend"].max())
    for i, r in s.iterrows():
        ax.text(max(r["limit"], r["spend"]) + xmax * 0.015, i, f"{inr(r['spend'])} / {inr(r['limit'])}  ({r['utilization_pct']:.0f}%)",
                va="center", fontsize=8, color=BAD if r["status"] == "Over budget" else INK)
    ax.set_yticks(y); ax.set_yticklabels(s["category"]); ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, xmax * 1.45); ax.xaxis.set_major_formatter(_short)
    ax.grid(axis="x", color=GRID); ax.set_axisbelow(True)
    return fig


def plot_cumulative_spend(df, month, total_budget: float | None = None, ax=None):
    """Cumulative spend through the month versus an even-pace budget line."""
    fig, ax = _fig(ax, (9, 4.6))
    d = analyze.daily_spend(df, month)
    ax.set_title(f"Cumulative spend - {_scope(month)}")
    if d.empty:
        _empty(ax); return fig
    ax.fill_between(d["date"], d["cumulative"], color=ACCENT, alpha=0.12)
    ax.plot(d["date"], d["cumulative"], color=ACCENT, lw=2.4, label="Actual")
    if total_budget:
        s, e = analyze.month_bounds(month)
        pace = pd.Series(np.linspace(total_budget / ((e - s).days + 1), total_budget, (e - s).days + 1),
                         index=pd.date_range(s, e))
        ax.plot(pace.index, pace.values, color=BAD, ls="--", lw=1.5, label=f"Budget pace ({inr(total_budget)})")
    ax.yaxis.set_major_formatter(_short); ax.grid(axis="y", color=GRID); ax.set_axisbelow(True)
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%d"))
    ax.legend(frameon=False, loc="upper left", fontsize=8.5)
    return fig


# ----------------------------------------------------------------------------
# One-page dashboard image
# ----------------------------------------------------------------------------
def _kpi_card(ax, title, value, sub, color=ACCENT, value_size=19):
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.set_axis_off()
    ax.add_patch(plt.Rectangle((0, 0), 1, 1, fc="#F8FAFC", ec=GRID, lw=1.2, transform=ax.transAxes))
    ax.add_patch(plt.Rectangle((0, 0), 0.02, 1, fc=color, ec="none", transform=ax.transAxes))
    ax.text(0.08, 0.80, title.upper(), fontsize=8.5, color=MUTED, fontweight="bold", va="center")
    ax.text(0.08, 0.50, value, fontsize=value_size, color=INK, fontweight="bold", va="center")
    ax.text(0.08, 0.17, sub, fontsize=8.5, color=MUTED, va="center")


def plot_dashboard(df, month, status=None, health=None):
    """Executive one-pager: KPI cards + 6 charts."""
    k = analyze.kpis(analyze.filter_month(df, month), analyze.period_days(df, month))
    fig = plt.figure(figsize=(17, 14), facecolor="white")
    gs = fig.add_gridspec(4, 6, height_ratios=[0.01, 3, 3, 3], hspace=0.42, wspace=0.9, left=0.05, right=0.97, top=0.845, bottom=0.04)
    fig.text(0.05, 0.965, "Personal Expense Tracker", fontsize=22, fontweight="bold", color=INK)
    fig.text(0.05, 0.94, f"Financial dashboard - {analyze.month_label(month)}  |  currency: INR", fontsize=11, color=MUTED)
    cards = [
        ("Total spend", inr(k["total_spend"]), f"{k['tx_count']} transactions  |  {inr(k['avg_daily_spend'])}/day", BAD, 19),
        ("Income", inr(k["income"]), "salary, freelance, refunds", GOOD, 19),
        ("Savings", inr(k["savings"]), f"savings rate {k['savings_rate']:.0f}%", ACCENT if k["savings"] >= 0 else BAD, 19),
        ("Top category", k["top_category"], f"{inr(k['top_category_amount'])}  ({k['top_category_share']:.0f}% of spend)", "#F59E0B", 15),
    ]
    if health:
        cards.append(("Health score", f"{health['score']}/100", health["label"],
                      GOOD if health["score"] >= 65 else "#F59E0B", 19))
    n, gap, left, width = len(cards), 0.012, 0.05, 0.92
    w = (width - gap * (n - 1)) / n
    for i, (t, v, sub, c, size) in enumerate(cards):
        _kpi_card(fig.add_axes([left + i * (w + gap), 0.862, w, 0.058]), t, v, sub, c, size)
    plot_category_bar(df, month, ax=fig.add_subplot(gs[1, 0:3]))
    plot_monthly_trend(df, ax=fig.add_subplot(gs[1, 3:6]), highlight=month)
    plot_payment_donut(df, month, ax=fig.add_subplot(gs[2, 0:2]))
    plot_daily_trend(df, month, ax=fig.add_subplot(gs[2, 2:6]))
    plot_budget_vs_actual(status, month, ax=fig.add_subplot(gs[3, 0:3]))
    plot_weekday_heatmap(df, month, ax=fig.add_subplot(gs[3, 3:6]))
    return fig


# ----------------------------------------------------------------------------
# Save everything
# ----------------------------------------------------------------------------
def save(fig, path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def generate_all_charts(df, month, status=None, health=None, out_dir=None) -> dict[str, Path]:
    """Create every chart as PNG. Returns {name: path}."""
    out = Path(out_dir or config.CHART_DIR)
    total_budget = float(status["limit"].sum()) if status is not None and len(status) else None
    figs = {
        "01_category_bar": plot_category_bar(df, month),
        "02_monthly_trend": plot_monthly_trend(df, highlight=month),
        "03_payment_method_donut": plot_payment_donut(df, month),
        "04_daily_spending_trend": plot_daily_trend(df, month),
        "05_category_donut": plot_category_donut(df, month),
        "06_weekday_category_heatmap": plot_weekday_heatmap(df, month),
        "07_budget_vs_actual": plot_budget_vs_actual(status, month),
        "08_cumulative_spend": plot_cumulative_spend(df, month, total_budget),
        "00_dashboard_summary": plot_dashboard(df, month, status, health),
    }
    return {name: save(fig, out / f"{name}.png") for name, fig in figs.items()}
