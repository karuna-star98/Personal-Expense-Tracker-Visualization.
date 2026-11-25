"""Monthly category budgets, overspend detection and alerts."""
from __future__ import annotations

import pandas as pd

from . import analyze, config, models
from .config import inr


def set_budget(month: str, category: str, limit: float, db_path=None) -> None:
    """Create or update the limit for one category in one month (YYYY-MM)."""
    pd.Period(month, "M")                       # validates the format
    if float(limit) < 0:
        raise ValueError("Budget limit cannot be negative.")
    models.init_db(db_path)
    with models.connect(db_path) as con:
        con.execute(
            """INSERT INTO budgets(month, category_name, limit_amount) VALUES (?,?,?)
               ON CONFLICT(month, category_name) DO UPDATE SET limit_amount=excluded.limit_amount""",
            (month, category, float(limit)))


def delete_budget(month: str, category: str, db_path=None) -> None:
    with models.connect(db_path) as con:
        con.execute("DELETE FROM budgets WHERE month=? AND category_name=?", (month, category))


def apply_default_budgets(months: list[str], db_path=None, overwrite: bool = False) -> int:
    """Seed the demo budget (config.DEFAULT_MONTHLY_BUDGET) for each month. Returns rows written."""
    models.init_db(db_path)
    n = 0
    with models.connect(db_path) as con:
        for m in months:
            for cat, limit in config.DEFAULT_MONTHLY_BUDGET.items():
                verb = "INSERT OR REPLACE" if overwrite else "INSERT OR IGNORE"
                cur = con.execute(f"{verb} INTO budgets(month, category_name, limit_amount) VALUES (?,?,?)",
                                  (m, cat, float(limit)))
                n += cur.rowcount
    return n


def copy_budgets(from_month: str, to_month: str, db_path=None) -> int:
    with models.connect(db_path) as con:
        cur = con.execute(
            """INSERT OR IGNORE INTO budgets(month, category_name, limit_amount)
               SELECT ?, category_name, limit_amount FROM budgets WHERE month=?""", (to_month, from_month))
        return cur.rowcount


def suggest_budgets(df: pd.DataFrame, month: str, lookback: int = 3, buffer: float = 0.10) -> pd.DataFrame:
    """Data-driven budget: average of the previous `lookback` months + a buffer, rounded to Rs 100."""
    prev = [m for m in analyze.complete_months(df) if m < month][-lookback:]
    if not prev:
        return pd.DataFrame(columns=["category", "avg_spend", "suggested_limit"])
    exp = analyze.expenses(df[df["month"].isin(prev)])
    avg = exp.groupby("category")["spend"].sum().div(len(prev)).rename("avg_spend")
    out = avg.to_frame()
    out["suggested_limit"] = ((out["avg_spend"] * (1 + buffer) / 100).round() * 100).astype(int)
    return out.sort_values("avg_spend", ascending=False).reset_index()


def get_budgets(month: str, db_path=None) -> pd.DataFrame:
    models.init_db(db_path)
    with models.connect(db_path) as con:
        return pd.read_sql_query(
            "SELECT category_name AS category, limit_amount FROM budgets WHERE month=? ORDER BY category_name",
            con, params=[month]).rename(columns={"limit_amount": "limit"})


def compute_status(spend: pd.DataFrame, budgets: pd.DataFrame, warn_at: float = 0.8,
                   include_unbudgeted: bool = False) -> pd.DataFrame:
    """Pure function: join spend [category, spend] with budgets [category, limit] and label each row.

    status: Over budget (> 100%), Warning (>= warn_at), On track, or No budget.
    """
    how = "outer" if include_unbudgeted else "left"
    merged = budgets.merge(spend, on="category", how=how)
    merged["spend"] = merged["spend"].fillna(0.0)
    merged["limit"] = merged["limit"].astype(float)
    merged["remaining"] = merged["limit"] - merged["spend"]
    merged["over_by"] = (merged["spend"] - merged["limit"]).clip(lower=0).fillna(0.0)
    merged["utilization_pct"] = (merged["spend"] / merged["limit"] * 100).where(merged["limit"] > 0)

    def status(r) -> str:
        if pd.isna(r["limit"]):
            return "No budget"
        if r["spend"] > r["limit"]:
            return "Over budget"
        return "Warning" if r["spend"] >= warn_at * r["limit"] else "On track"

    merged["status"] = merged.apply(status, axis=1) if len(merged) else pd.Series(dtype="object")
    return merged.sort_values(["over_by", "utilization_pct"], ascending=False).reset_index(drop=True)[
        ["category", "limit", "spend", "remaining", "over_by", "utilization_pct", "status"]]


def status_from_frame(df_month: pd.DataFrame, budgets: pd.DataFrame, **kw) -> pd.DataFrame:
    """Same as check_budget but uses an already-filtered transactions frame (e.g. one account only)."""
    exp = df_month[df_month["amount"] < 0]
    spend = (-exp.groupby("category")["amount"].sum()).rename("spend").reset_index()
    return compute_status(spend, budgets, **kw)


def check_budget(month: str, db_path=None, warn_at: float = 0.8, include_unbudgeted: bool = False) -> pd.DataFrame:
    """Compare actual spend (from the database) with limits for one month."""
    models.init_db(db_path)
    with models.connect(db_path) as con:
        spend = pd.read_sql_query(
            """SELECT COALESCE(c.name,'Uncategorized') AS category, -SUM(t.amount) AS spend
               FROM transactions t LEFT JOIN categories c ON c.id = t.category_id
               WHERE t.amount < 0 AND strftime('%Y-%m', t.tx_date) = ? GROUP BY 1""", con, params=[month])
    return compute_status(spend, get_budgets(month, db_path), warn_at, include_unbudgeted)


def budget_alerts(status: pd.DataFrame) -> list[str]:
    """Short alert messages, worst first (what an SMS/e-mail alert would say)."""
    alerts = []
    for r in status.itertuples():
        if r.status == "Over budget":
            alerts.append(f"OVER: {r.category} is {inr(r.over_by)} over its {inr(r.limit)} budget "
                          f"({r.utilization_pct:.0f}% used).")
    for r in status.itertuples():
        if r.status == "Warning":
            alerts.append(f"WARNING: {r.category} has used {r.utilization_pct:.0f}% of its budget "
                          f"({inr(r.remaining)} left).")
    return alerts
