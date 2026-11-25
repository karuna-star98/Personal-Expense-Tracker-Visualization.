#!/usr/bin/env python3
"""Personal Expense Tracker - command line interface.

Quick start:
    python main.py run-all          # build demo DB, analyze, make charts + reports
    python main.py dashboard        # open the Streamlit dashboard
    python main.py --help           # every command
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date

import pandas as pd

from src import analyze, budget, categorize, config, generate_data, ingest, models, pipeline, plots, report
from src.config import inr

BAR = "=" * 66


def header(title: str) -> None:
    print(f"\n{BAR}\n  {title}\n{BAR}")


def resolve_month(df: pd.DataFrame, month: str | None) -> str:
    m = month or analyze.default_month(df)
    if not m or (m not in set(df["month"])):
        sys.exit(f"No data for month '{m}'. Available: {', '.join(sorted(df['month'].unique())) or 'none - run `python main.py run-all`'}")
    return m


# ----------------------------------------------------------------------------
# Terminal summary
# ----------------------------------------------------------------------------
def print_analysis(df: pd.DataFrame, month: str) -> dict:
    status = budget.check_budget(month)
    S = report.build_summary(month, df=df)
    k, h = S["kpis"], S["health"]
    header(f"EXPENSE ANALYSIS - {analyze.month_label(month)}")
    print(f"  Total spend          : {inr(k['total_spend']):>12}")
    print(f"  Income               : {inr(k['income']):>12}")
    print(f"  Savings              : {inr(k['savings']):>12}   ({k['savings_rate']:.1f}% savings rate)")
    print(f"  Avg daily spend      : {inr(k['avg_daily_spend']):>12}   over {k['days']} days")
    print(f"  Highest category     : {k['top_category']} ({inr(k['top_category_amount'])}, {k['top_category_share']:.0f}%)")
    print(f"  Health score         : {h['score']}/100 ({h['label']})")

    print("\n  CATEGORY-WISE SPENDING")
    for r in S["category"].itertuples():
        bar = "#" * max(1, int(r.share_pct / 2.5))
        print(f"   {r.category:<20}{inr(r.spend):>11}  {r.share_pct:5.1f}%  {bar}")

    print("\n  PAYMENT METHODS")
    for r in S["payment"].itertuples():
        print(f"   {r.payment_method:<20}{inr(r.spend):>11}  {r.share_pct:5.1f}%")

    print("\n  MONTHLY TREND (last 6 complete months)")
    ms = S["monthly"][S["monthly"]["month"].isin(analyze.complete_months(df))].tail(6)
    for r in ms.itertuples():
        chg = "" if pd.isna(r.mom_change_pct) else f"{r.mom_change_pct:+.0f}%"
        print(f"   {analyze.month_label(r.month):<10} spend {inr(r.spend):>10}   income {inr(r.income):>10}   {chg:>5}")

    if S["alerts"]:
        print("\n  BUDGET ALERTS")
        for a in S["alerts"][:6]:
            print(f"   ! {a}")

    print("\n  KEY INSIGHTS")
    for t in S["insights"]:
        print(f"   * {t}")
    fc = S["forecast"]
    if fc["next_month"]:
        print(f"\n  FORECAST {analyze.month_label(fc['next_month'])}: about {inr(fc['total'])} "
              f"(trend check {inr(fc['trend_total'])})")
    return S


def print_generated(res: dict) -> None:
    header("FILES CREATED")
    for name, p in res["charts"].items():
        print(f"   chart   {p.relative_to(config.ROOT)}")
    for p in res["csv"].values():
        print(f"   csv     {p.relative_to(config.ROOT)}")
    for key in ("excel", "html", "text"):
        print(f"   report  {res[key].relative_to(config.ROOT)}")
    print(f"   images  {config.IMAGES_DIR.relative_to(config.ROOT)}/  (copied for README)")


# ----------------------------------------------------------------------------
# Commands
# ----------------------------------------------------------------------------
def cmd_run_all(a) -> None:
    header("STEP 1/6  LOAD DATA  (synthetic demo dataset -> SQLite)")
    out = pipeline.load_demo(reset=not a.keep_db, regenerate=a.regenerate)
    s, b = out["sample_import"], out["bank_import"]
    print(f"   sample_expenses.csv : {s['rows_read']} rows read, {s['inserted']} inserted")
    print(f"   bank statement      : {b['rows_read']} rows read -> dropped {b['dropped_invalid']} invalid, "
          f"{b['duplicates_removed']} duplicate, {b['inserted']} inserted")
    c = out["categorize"]
    print(f"   categorized         : {c['processed']} transactions, {c['uncategorized']} left Uncategorized")
    if isinstance(c.get("ml"), dict) and "cv_accuracy" in c["ml"]:
        print(f"   ML fallback         : CV accuracy {c['ml']['cv_accuracy']:.1%}, labelled {c['ml']['applied']} extra")
    print(f"   budgets             : {out['budgets_created']} monthly category limits created")
    df = analyze.fetch_frame()
    month = a.month or out["default_month"]
    header("STEP 2/6  CLEAN DATA CHECK")
    print(f"   transactions : {len(df)}   range: {df['tx_date'].min():%d %b %Y} -> {df['tx_date'].max():%d %b %Y}")
    print(f"   months       : {df['month'].nunique()}   accounts: {', '.join(sorted(df['account'].unique()))}")
    print(f"   report month : {analyze.month_label(month)}")
    header("STEP 3/6  ANALYZE")
    print_analysis(df, month)
    header("STEP 4-6/6  CHARTS, REPORTS, EXPORTS")
    res = report.generate_all(month, df=df)
    print_generated(res)
    print("\n  Done. Next: python main.py dashboard\n")


def cmd_generate(a) -> None:
    r = generate_data.write_sample_files(seed=a.seed)
    print(f"Wrote {r['sample']} ({r['rows_sample']} rows) and {r['bank']} ({r['rows_bank']} rows)")


def cmd_ingest(a) -> None:
    rep = ingest.import_csv(a.csv, account=a.account, dayfirst=not a.monthfirst, expenses_positive=a.expenses_positive)
    c = categorize.run(use_ml=a.ml)
    print(f"Read {rep['rows_read']} rows | invalid dropped {rep['dropped_invalid']} | duplicates removed "
          f"{rep['duplicates_removed']} | inserted {rep['inserted']} | already in DB {rep['skipped']}")
    print(f"Categorized {c['processed']} | still uncategorized {c['uncategorized']}")


def cmd_categorize(a) -> None:
    print(categorize.run(recategorize=a.all, use_ml=a.ml))


def cmd_add(a) -> None:
    ok = ingest.add_manual_transaction(a.date, a.description, a.amount, a.type, a.category, a.method, a.account)
    categorize.run()
    print("Added." if ok else "Skipped: identical transaction already exists.")


def cmd_budget(a) -> None:
    models.init_db()
    df = analyze.fetch_frame()
    if a.action == "set":
        budget.set_budget(a.month, a.category, a.limit)
        print(f"Budget for {a.category} in {a.month} = {inr(a.limit)}")
    elif a.action == "suggest":
        print(budget.suggest_budgets(df, a.month).to_string(index=False))
    else:
        month = resolve_month(df, a.month)
        st = budget.check_budget(month)
        header(f"BUDGET CHECK - {analyze.month_label(month)}")
        for r in st.itertuples():
            print(f"   {r.category:<20}{inr(r.spend):>10} / {inr(r.limit):<9}{r.utilization_pct:>5.0f}%  {r.status}")
        for al in budget.budget_alerts(st):
            print(f"   ! {al}")


def cmd_analyze(a) -> None:
    df = analyze.fetch_frame()
    print_analysis(df, resolve_month(df, a.month))


def cmd_charts(a) -> None:
    df = analyze.fetch_frame()
    month = resolve_month(df, a.month)
    status = budget.check_budget(month)
    health = analyze.financial_health_score(df, month, status)
    for name, p in plots.generate_all_charts(df, month, status, health).items():
        print("saved", p.relative_to(config.ROOT))


def cmd_report(a) -> None:
    df = analyze.fetch_frame()
    res = report.generate_all(resolve_month(df, a.month), df=df)
    print_generated(res)


def cmd_dashboard(_a) -> None:
    app = config.ROOT / "src" / "app_streamlit.py"
    sys.exit(subprocess.call([sys.executable, "-m", "streamlit", "run", str(app)], cwd=config.ROOT))   # cwd -> picks up .streamlit/config.toml


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Personal Expense Tracker with Data Visualization")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("run-all", help="demo pipeline: data -> DB -> analysis -> charts -> reports")
    s.add_argument("--month", help="YYYY-MM (default: latest complete month)")
    s.add_argument("--keep-db", action="store_true", help="do not wipe the existing database first")
    s.add_argument("--regenerate", action="store_true", help="re-create the synthetic CSV files")
    s.set_defaults(func=cmd_run_all)

    s = sub.add_parser("generate", help="write synthetic CSV files to data/")
    s.add_argument("--seed", type=int, default=42)
    s.set_defaults(func=cmd_generate)

    s = sub.add_parser("ingest", help="import any bank/UPI CSV (columns auto-detected)")
    s.add_argument("csv"); s.add_argument("--account", default=None)
    s.add_argument("--monthfirst", action="store_true", help="dates are mm/dd/yyyy (default dd/mm/yyyy)")
    s.add_argument("--expenses-positive", action="store_true", help="file lists expenses as positive numbers")
    s.add_argument("--ml", action="store_true", help="use Naive-Bayes fallback for unknown merchants")
    s.set_defaults(func=cmd_ingest)

    s = sub.add_parser("categorize", help="auto-categorize uncategorized rows")
    s.add_argument("--all", action="store_true", help="re-run rules on rule/ml-labelled rows"); s.add_argument("--ml", action="store_true")
    s.set_defaults(func=cmd_categorize)

    s = sub.add_parser("add", help="add one transaction manually")
    s.add_argument("--date", default=str(date.today())); s.add_argument("--amount", type=float, required=True)
    s.add_argument("--description", required=True); s.add_argument("--type", choices=["expense", "income"], default="expense")
    s.add_argument("--category"); s.add_argument("--method", default="UPI"); s.add_argument("--account", default="Manual")
    s.set_defaults(func=cmd_add)

    s = sub.add_parser("budget", help="set / check / suggest monthly budgets")
    s.add_argument("action", choices=["set", "check", "suggest"]); s.add_argument("--month")
    s.add_argument("--category"); s.add_argument("--limit", type=float)
    s.set_defaults(func=cmd_budget)

    for name, fn, h in (("analyze", cmd_analyze, "print the analysis in the terminal"),
                        ("charts", cmd_charts, "save all PNG charts"), ("report", cmd_report, "charts + Excel/HTML/TXT reports")):
        s = sub.add_parser(name, help=h); s.add_argument("--month", help="YYYY-MM"); s.set_defaults(func=fn)

    s = sub.add_parser("dashboard", help="launch the Streamlit dashboard"); s.set_defaults(func=cmd_dashboard)
    return p


def main(argv=None) -> None:
    a = build_parser().parse_args(argv)
    if a.cmd == "budget" and a.action == "set" and not (a.month and a.category and a.limit is not None):
        sys.exit("budget set needs --month, --category and --limit")
    a.func(a)


if __name__ == "__main__":
    main()
