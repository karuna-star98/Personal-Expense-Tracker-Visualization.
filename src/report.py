"""Report generation: Excel workbook, HTML report, plain-text summary and CSV exports."""
from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path

import pandas as pd
from jinja2 import Environment

from . import analyze, budget, config, plots
from .config import inr


# ----------------------------------------------------------------------------
# One place that collects every number a report needs
# ----------------------------------------------------------------------------
def build_summary(month: str, db_path=None, df: pd.DataFrame | None = None) -> dict:
    df = analyze.fetch_frame(db_path) if df is None else df
    m = analyze.filter_month(df, month)
    status = budget.check_budget(month, db_path)
    k = analyze.kpis(m, analyze.period_days(df, month))
    return {
        "month": month, "label": analyze.month_label(month), "df": df, "month_df": m, "kpis": k,
        "category": analyze.category_summary(df, month), "payment": analyze.payment_summary(df, month),
        "monthly": analyze.monthly_summary(df), "merchants": analyze.top_merchants(df, month, 8),
        "budget": status, "alerts": budget.budget_alerts(status),
        "recurring": analyze.detect_recurring(df), "anomalies": analyze.detect_anomalies(df),
        "forecast": analyze.forecast_next_month(df),
        "health": analyze.financial_health_score(df, month, status),
        "insights": analyze.generate_insights(df, month, status),
        "generated": datetime.now().strftime("%d %b %Y, %H:%M"),
    }


def _round(frame: pd.DataFrame) -> pd.DataFrame:
    """Round only float columns (rounding date columns raises a warning)."""
    return frame.apply(lambda c: c.round(2) if pd.api.types.is_float_dtype(c) else c)


def _outdir(path, default_dir) -> Path:
    p = Path(path) if path else Path(default_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


# ----------------------------------------------------------------------------
# CSV exports
# ----------------------------------------------------------------------------
def export_csvs(S: dict, out_dir=None) -> dict[str, Path]:
    out = Path(out_dir or config.OUTPUT_DIR)
    out.mkdir(parents=True, exist_ok=True)
    files = {
        f"category_summary_{S['month']}.csv": S["category"], "monthly_summary.csv": S["monthly"],
        f"payment_summary_{S['month']}.csv": S["payment"], f"budget_status_{S['month']}.csv": S["budget"],
        "recurring_payments.csv": S["recurring"], "anomalies.csv": S["anomalies"],
    }
    paths = {}
    for name, frame in files.items():
        paths[name] = out / name
        _round(frame).to_csv(paths[name], index=False)
    return paths


# ----------------------------------------------------------------------------
# Excel
# ----------------------------------------------------------------------------
def export_excel(S: dict, path=None) -> Path:
    """Multi-sheet formatted workbook with native Excel charts."""
    path = _outdir(path, config.REPORT_DIR / f"expense_report_{S['month']}.xlsx")
    tx = S["month_df"][["tx_date", "description", "category", "amount", "payment_method", "account"]].copy()
    tx["tx_date"] = tx["tx_date"].dt.date
    tx = tx.rename(columns={"tx_date": "Date", "description": "Description", "category": "Category",
                            "amount": "Amount (INR)", "payment_method": "Payment Method", "account": "Account"})

    sheets = {
        "Transactions": (tx, ["Amount (INR)"], []),
        "Category Summary": (S["category"].rename(columns=str.title).rename(columns={
            "Share_Pct": "Share %", "Tx_Count": "Transactions", "Avg_Tx": "Avg Transaction", "Max_Tx": "Largest"}),
            ["Spend", "Avg Transaction", "Largest"], ["Share %"]),
        "Monthly Trend": (S["monthly"].rename(columns={"month": "Month", "income": "Income", "spend": "Spend",
                          "savings": "Savings", "savings_rate": "Savings Rate %", "tx_count": "Transactions",
                          "mom_change_pct": "MoM Change %"}),
                          ["Income", "Spend", "Savings"], ["Savings Rate %", "MoM Change %"]),
        "Payment Methods": (S["payment"].rename(columns={"payment_method": "Payment Method", "spend": "Spend",
                            "share_pct": "Share %", "tx_count": "Transactions"}), ["Spend"], ["Share %"]),
        "Budget Check": (S["budget"].rename(columns={"category": "Category", "limit": "Budget", "spend": "Spent",
                         "remaining": "Remaining", "over_by": "Over By", "utilization_pct": "Used %",
                         "status": "Status"}), ["Budget", "Spent", "Remaining", "Over By"], ["Used %"]),
        "Recurring": (S["recurring"].assign(last_date=lambda d: d["last_date"].dt.date,
                      next_expected=lambda d: d["next_expected"].dt.date), ["avg_amount", "annual_cost"], []),
        "Anomalies": (S["anomalies"].assign(tx_date=lambda d: d["tx_date"].dt.date), ["spend", "typical"], []),
    }
    fc = S["forecast"]["by_category"]
    if len(fc):
        sheets["Forecast"] = (fc.rename(columns={"category": "Category", "forecast": f"Forecast {S['forecast']['next_month']}"}),
                              [f"Forecast {S['forecast']['next_month']}"], [])

    with pd.ExcelWriter(path, engine="xlsxwriter", datetime_format="yyyy-mm-dd", date_format="yyyy-mm-dd") as xw:
        wb = xw.book
        f_title = wb.add_format({"bold": True, "font_size": 18, "font_color": "#0F172A"})
        f_sub = wb.add_format({"font_color": "#64748B"})
        f_head = wb.add_format({"bold": True, "font_color": "white", "bg_color": "#4F46E5", "border": 1, "align": "center"})
        f_money = wb.add_format({"num_format": "#,##0.00"})
        f_pct = wb.add_format({"num_format": '0.0"%"'})
        f_label = wb.add_format({"bold": True, "bg_color": "#F1F5F9", "border": 1})
        f_val = wb.add_format({"border": 1, "num_format": "#,##0"})
        f_wrap = wb.add_format({"text_wrap": True, "valign": "top"})

        # ---- Summary sheet (created first so it is the first tab) ----
        ws = wb.add_worksheet("Summary")
        k, h = S["kpis"], S["health"]
        ws.write("A1", "Personal Expense Report", f_title)
        ws.write("A2", f"Period: {S['label']}   |   Generated: {S['generated']}   |   Currency: INR", f_sub)
        rows = [("Total spend", k["total_spend"]), ("Income", k["income"]), ("Savings", k["savings"]),
                ("Savings rate (%)", round(k["savings_rate"], 1)), ("Expense transactions", k["tx_count"]),
                ("Average per transaction", round(k["avg_transaction"])), ("Average daily spend", round(k["avg_daily_spend"])),
                ("Top category", f"{k['top_category']} ({k['top_category_share']:.0f}%)"),
                ("Financial health score", f"{h['score']}/100 - {h['label']}")]
        for i, (lab, val) in enumerate(rows):
            ws.write(3 + i, 0, lab, f_label)
            ws.write(3 + i, 1, val, f_val)
        ws.write(13, 0, "Key insights", wb.add_format({"bold": True, "font_size": 13}))
        for i, text in enumerate(S["insights"]):
            ws.merge_range(14 + i, 0, 14 + i, 7, f"- {text}", f_wrap)
            ws.set_row(14 + i, 30)
        ws.set_column("A:A", 28); ws.set_column("B:B", 30); ws.set_column("C:H", 14)

        # ---- data sheets ----
        for name, (frame, money, pct) in sheets.items():
            frame = _round(frame)
            frame.to_excel(xw, sheet_name=name, index=False)
            sh = xw.sheets[name]
            for c, col in enumerate(frame.columns):
                sh.write(0, c, col, f_head)
                width = max([len(str(col))] + [len(str(v)) for v in frame[col].head(200)]) + 3
                fmt = f_money if col in money else f_pct if col in pct else None
                sh.set_column(c, c, min(width, 55), fmt)
            sh.freeze_panes(1, 0)
            if len(frame):
                sh.autofilter(0, 0, len(frame), len(frame.columns) - 1)
        bs = xw.sheets["Budget Check"]
        if len(S["budget"]):
            n = len(S["budget"]); col = list(S["budget"].columns).index("status")
            for text, bg in (("Over budget", "#FECACA"), ("Warning", "#FDE68A"), ("On track", "#BBF7D0")):
                bs.conditional_format(1, col, n, col, {"type": "cell", "criteria": "==", "value": f'"{text}"',
                                                       "format": wb.add_format({"bg_color": bg})})

        # ---- native Excel charts on Summary ----
        nc = len(S["category"])
        if nc:
            ch = wb.add_chart({"type": "bar"})
            ch.add_series({"name": "Spend", "categories": ["Category Summary", 1, 0, nc, 0],
                           "values": ["Category Summary", 1, 1, nc, 1], "fill": {"color": "#4F46E5"}})
            ch.set_title({"name": f"Spending by category - {S['label']}"}); ch.set_legend({"none": True})
            ch.set_y_axis({"reverse": True}); ch.set_size({"width": 560, "height": 340})
            ws.insert_chart("D4", ch)
        nm = len(S["monthly"])
        if nm:
            ch2 = wb.add_chart({"type": "line"})
            for col, color, nm_ in ((2, "#4F46E5", "Spend"), (1, "#10B981", "Income")):
                ch2.add_series({"name": nm_, "categories": ["Monthly Trend", 1, 0, nm, 0],
                                "values": ["Monthly Trend", 1, col, nm, col], "line": {"color": color, "width": 2.25},
                                "marker": {"type": "circle", "size": 5}})
            ch2.set_title({"name": "Monthly income vs spending"}); ch2.set_size({"width": 560, "height": 320})
            ws.insert_chart("D22", ch2)
    return path


# ----------------------------------------------------------------------------
# Plain text
# ----------------------------------------------------------------------------
def export_text(S: dict, path=None) -> Path:
    path = _outdir(path, config.REPORT_DIR / f"expense_report_{S['month']}.txt")
    k, h = S["kpis"], S["health"]
    line = "=" * 64
    out = [line, f"  PERSONAL EXPENSE REPORT - {S['label'].upper()}", f"  Generated {S['generated']}", line, "",
           "SUMMARY", "-" * 64,
           f"  Total spend            : {inr(k['total_spend']):>14}",
           f"  Income                 : {inr(k['income']):>14}",
           f"  Savings                : {inr(k['savings']):>14}   ({k['savings_rate']:.1f}% savings rate)",
           f"  Average daily spend    : {inr(k['avg_daily_spend']):>14}",
           f"  Expense transactions   : {k['tx_count']:>14}",
           f"  Highest category       : {k['top_category']} ({inr(k['top_category_amount'])}, {k['top_category_share']:.0f}%)",
           f"  Financial health score : {h['score']}/100 ({h['label']})", "",
           "CATEGORY-WISE SPENDING", "-" * 64]
    out += [f"  {r.category:<22}{inr(r.spend):>12}  {r.share_pct:>5.1f}%  ({r.tx_count} txns)" for r in S["category"].itertuples()]
    out += ["", "PAYMENT METHODS", "-" * 64]
    out += [f"  {r.payment_method:<22}{inr(r.spend):>12}  {r.share_pct:>5.1f}%" for r in S["payment"].itertuples()]
    out += ["", "BUDGET STATUS", "-" * 64]
    if len(S["budget"]):
        out += [f"  {r.category:<22}{inr(r.spend):>10} / {inr(r.limit):<9} {r.utilization_pct:>5.0f}%  {r.status}"
                for r in S["budget"].itertuples()]
    else:
        out.append("  No budgets set for this month.")
    out += ["", "ALERTS", "-" * 64] + [f"  ! {a}" for a in S["alerts"]] if S["alerts"] else []
    out += ["", "KEY INSIGHTS", "-" * 64] + [f"  * {t}" for t in S["insights"]]
    fc = S["forecast"]
    if fc["next_month"]:
        out += ["", f"FORECAST - {analyze.month_label(fc['next_month'])}", "-" * 64,
                f"  Expected spend (weighted 3-month average): {inr(fc['total'])}",
                f"  Linear-trend cross-check                 : {inr(fc['trend_total'])}"]
    out += ["", line]
    path.write_text("\n".join(out), encoding="utf-8")
    return path


# ----------------------------------------------------------------------------
# HTML
# ----------------------------------------------------------------------------
HTML_TEMPLATE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Expense Report - {{ S.label }}</title>
<style>
:root{--ink:#0f172a;--muted:#64748b;--line:#e2e8f0;--bg:#f8fafc;--accent:#4f46e5;--good:#059669;--bad:#dc2626;--warn:#d97706}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1100px;margin:0 auto;padding:32px 24px 60px}
header{display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:24px}
h1{margin:0;font-size:28px}h2{margin:36px 0 12px;font-size:18px}.sub{color:var(--muted);font-size:13px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px}
.card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:16px 18px}
.card .l{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);font-weight:700}
.card .v{font-size:26px;font-weight:700;margin-top:2px}.card .s{font-size:12px;color:var(--muted)}
.good{color:var(--good)}.bad{color:var(--bad)}
ul.ins{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px 22px 14px 38px}ul.ins li{margin:6px 0}
table{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);border-radius:12px;overflow:hidden;font-size:14px}
th{background:#eef2ff;color:#3730a3;text-align:left;padding:9px 12px;font-size:12px;text-transform:uppercase;letter-spacing:.04em}
td{padding:8px 12px;border-top:1px solid var(--line)}td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
.pill{padding:2px 9px;border-radius:99px;font-size:12px;font-weight:600}
.Over{background:#fee2e2;color:#991b1b}.Warning{background:#fef3c7;color:#92400e}.On{background:#d1fae5;color:#065f46}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}@media(max-width:820px){.grid2{grid-template-columns:1fr}}
img{width:100%;border:1px solid var(--line);border-radius:12px;background:#fff}
footer{margin-top:40px;color:var(--muted);font-size:12px;text-align:center}
@media print{body{background:#fff}.wrap{padding:0}h2{break-after:avoid}img,table,.card{break-inside:avoid}}
</style></head><body><div class="wrap">
<header><div><h1>Personal Expense Report</h1><div class="sub">{{ S.label }} &middot; generated {{ S.generated }} &middot; currency INR</div></div>
<div class="sub">Health score <b style="font-size:22px;color:var(--ink)">{{ S.health.score }}/100</b> &middot; {{ S.health.label }}</div></header>
<div class="kpis">
 <div class="card"><div class="l">Total spend</div><div class="v">{{ inr(k.total_spend) }}</div><div class="s">{{ k.tx_count }} transactions</div></div>
 <div class="card"><div class="l">Income</div><div class="v">{{ inr(k.income) }}</div><div class="s">&nbsp;</div></div>
 <div class="card"><div class="l">Savings</div><div class="v {{ 'good' if k.savings>=0 else 'bad' }}">{{ inr(k.savings) }}</div><div class="s">{{ '%.0f'|format(k.savings_rate) }}% savings rate</div></div>
 <div class="card"><div class="l">Avg daily spend</div><div class="v">{{ inr(k.avg_daily_spend) }}</div><div class="s">over {{ k.days }} days</div></div>
 <div class="card"><div class="l">Top category</div><div class="v" style="font-size:19px;padding:5px 0">{{ k.top_category }}</div><div class="s">{{ inr(k.top_category_amount) }} ({{ '%.0f'|format(k.top_category_share) }}%)</div></div>
</div>
<h2>Key insights</h2><ul class="ins">{% for t in S.insights %}<li>{{ t }}</li>{% endfor %}</ul>
{% if S.alerts %}<h2>Budget alerts</h2><ul class="ins">{% for a in S.alerts %}<li>{{ a }}</li>{% endfor %}</ul>{% endif %}
<h2>Overview</h2><img alt="Dashboard summary" src="data:image/png;base64,{{ imgs['00_dashboard_summary'] }}">
<h2>Category-wise spending</h2><div class="grid2"><img alt="Category bar" src="data:image/png;base64,{{ imgs['01_category_bar'] }}">
<table><tr><th>Category</th><th class="n">Spend</th><th class="n">Share</th><th class="n">Txns</th></tr>
{% for r in S.category.itertuples() %}<tr><td>{{ r.category }}</td><td class="n">{{ inr(r.spend) }}</td><td class="n">{{ '%.1f'|format(r.share_pct) }}%</td><td class="n">{{ r.tx_count }}</td></tr>{% endfor %}</table></div>
<h2>Trends</h2><div class="grid2"><img alt="Monthly trend" src="data:image/png;base64,{{ imgs['02_monthly_trend'] }}"><img alt="Daily trend" src="data:image/png;base64,{{ imgs['04_daily_spending_trend'] }}"></div>
<h2>Budget vs actual</h2><div class="grid2"><img alt="Budget" src="data:image/png;base64,{{ imgs['07_budget_vs_actual'] }}">
<table><tr><th>Category</th><th class="n">Spent</th><th class="n">Budget</th><th>Status</th></tr>
{% for r in S.budget.itertuples() %}<tr><td>{{ r.category }}</td><td class="n">{{ inr(r.spend) }}</td><td class="n">{{ inr(r.limit) }}</td><td><span class="pill {{ r.status.split()[0] }}">{{ r.status }}</span></td></tr>{% endfor %}</table></div>
{% if S.recurring|length %}<h2>Recurring payments (subscriptions &amp; bills)</h2>
<table><tr><th>Merchant</th><th>Category</th><th class="n">Avg amount</th><th class="n">Yearly cost</th><th>Next expected</th></tr>
{% for r in S.recurring.itertuples() %}<tr><td>{{ r.merchant }}</td><td>{{ r.category }}</td><td class="n">{{ inr(r.avg_amount) }}</td><td class="n">{{ inr(r.annual_cost) }}</td><td>{{ r.next_expected.strftime('%d %b %Y') }}</td></tr>{% endfor %}</table>{% endif %}
{% if S.forecast.next_month %}<h2>Forecast for {{ month_label(S.forecast.next_month) }}</h2>
<div class="card">Expected spend <b>{{ inr(S.forecast.total) }}</b> (weighted average of the last 3 complete months). Linear-trend cross-check: <b>{{ inr(S.forecast.trend_total) }}</b>.</div>{% endif %}
<footer>Personal Expense Tracker &middot; Python, pandas, SQLite, Matplotlib &middot; synthetic demo data</footer>
</div></body></html>"""


def _b64(path: Path) -> str:
    return base64.b64encode(Path(path).read_bytes()).decode()


def export_html(S: dict, path=None, charts: dict | None = None) -> Path:
    path = _outdir(path, config.REPORT_DIR / f"expense_report_{S['month']}.html")
    if charts is None:
        charts = plots.generate_all_charts(S["df"], S["month"], S["budget"], S["health"])
    imgs = {name: _b64(p) for name, p in charts.items()}
    env = Environment(autoescape=True)
    html = env.from_string(HTML_TEMPLATE).render(S=S, k=S["kpis"], imgs=imgs, inr=inr, month_label=analyze.month_label)
    path.write_text(html, encoding="utf-8")
    return path


# ----------------------------------------------------------------------------
# Everything at once
# ----------------------------------------------------------------------------
def generate_all(month: str, db_path=None, df: pd.DataFrame | None = None, copy_images: bool = True) -> dict:
    """Charts + CSVs + Excel + HTML + TXT for one month. Returns a dict of created paths."""
    config.ensure_dirs()
    S = build_summary(month, db_path, df)
    charts = plots.generate_all_charts(S["df"], month, S["budget"], S["health"])
    result = {"charts": charts, "csv": export_csvs(S), "excel": export_excel(S), "html": export_html(S, charts=charts),
              "text": export_text(S), "summary": S}
    if copy_images:          # README images live in images/ (committed to GitHub as proof of work)
        import shutil
        for name, p in charts.items():
            shutil.copy(p, config.IMAGES_DIR / f"{name}.png")
    return result
