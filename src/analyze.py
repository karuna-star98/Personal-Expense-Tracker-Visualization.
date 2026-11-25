"""Analytics layer: KPIs, summaries, recurring payments, anomalies, forecast, health score, insights.

Convention (same as the database): amount < 0 is an expense, amount > 0 is income.
Helper frames add a positive `spend` column so charts and sums are easy to read.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from . import config, models
from .config import inr

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
FRAME_COLUMNS = ["id", "tx_date", "description", "amount", "account", "payment_method",
                 "category", "category_source", "month", "weekday", "is_weekend"]


# ----------------------------------------------------------------------------
# Loading
# ----------------------------------------------------------------------------
def fetch_frame(db_path=None) -> pd.DataFrame:
    """Load all transactions (joined with category names) into a tidy DataFrame."""
    models.init_db(db_path)
    with models.connect(db_path) as con:
        df = pd.read_sql_query(
            """SELECT t.id, t.tx_date, t.description, t.amount, t.account, t.payment_method,
                      COALESCE(c.name, 'Uncategorized') AS category, t.category_source
               FROM transactions t LEFT JOIN categories c ON c.id = t.category_id
               ORDER BY t.tx_date, t.id""", con)
    return prepare_frame(df)


def prepare_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived columns (month, weekday ...). Works on any frame with tx_date + amount."""
    df = df.copy()
    if df.empty:
        return pd.DataFrame({c: pd.Series(dtype="object") for c in FRAME_COLUMNS})
    df["tx_date"] = pd.to_datetime(df["tx_date"])
    df["month"] = df["tx_date"].dt.to_period("M").astype(str)
    df["weekday"] = df["tx_date"].dt.dayofweek.map(dict(enumerate(WEEKDAYS)))
    df["is_weekend"] = df["tx_date"].dt.dayofweek >= 5
    for col, default in (("category", "Uncategorized"), ("payment_method", "Other"), ("account", "Manual")):
        if col not in df:
            df[col] = default
    return df


def expenses(df: pd.DataFrame) -> pd.DataFrame:
    out = df[df["amount"] < 0].copy()
    out["spend"] = -out["amount"]
    return out


def incomes(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["amount"] > 0].copy()


# ----------------------------------------------------------------------------
# Period helpers
# ----------------------------------------------------------------------------
def month_label(month: str) -> str:
    """'2026-10' -> 'Oct 2026'."""
    return pd.Period(month, "M").strftime("%b %Y")


def month_bounds(month: str, data_end: pd.Timestamp | None = None) -> tuple[pd.Timestamp, pd.Timestamp]:
    start = pd.Period(month, "M").start_time.normalize()
    end = pd.Period(month, "M").end_time.normalize()
    if data_end is not None and start <= data_end < end:
        end = data_end.normalize()                 # month still in progress
    return start, end


def complete_months(df: pd.DataFrame) -> list[str]:
    """Months that are fully covered by the data (the latest month may be partial)."""
    if df.empty:
        return []
    last = df["tx_date"].max().normalize()
    out = []
    for m in sorted(df["month"].unique()):
        if pd.Period(m, "M").end_time.normalize() <= last:
            out.append(m)
    return out


def default_month(df: pd.DataFrame) -> str | None:
    """Latest *complete* month, falling back to the latest month with data."""
    full = complete_months(df)
    if full:
        return full[-1]
    return sorted(df["month"].unique())[-1] if not df.empty else None


def filter_month(df: pd.DataFrame, month: str | None) -> pd.DataFrame:
    return df if not month else df[df["month"] == month]


def period_days(df_all: pd.DataFrame, month: str | None) -> int:
    """Number of days to divide by when computing 'average per day'."""
    if df_all.empty:
        return 1
    if month:
        s, e = month_bounds(month, df_all["tx_date"].max())
    else:
        s, e = df_all["tx_date"].min(), df_all["tx_date"].max()
    return max(int((e - s).days) + 1, 1)


# ----------------------------------------------------------------------------
# KPIs and summaries
# ----------------------------------------------------------------------------
def kpis(df: pd.DataFrame, days: int | None = None) -> dict:
    exp, inc = expenses(df), incomes(df)
    total_spend, income = float(exp["spend"].sum()), float(inc["amount"].sum())
    by_cat = exp.groupby("category")["spend"].sum().sort_values(ascending=False)
    if days is None:
        days = max((df["tx_date"].max() - df["tx_date"].min()).days + 1, 1) if len(df) else 1
    top_cat = by_cat.index[0] if len(by_cat) else "-"
    biggest = exp.loc[exp["spend"].idxmax()] if len(exp) else None
    return {
        "total_spend": total_spend, "income": income, "savings": income - total_spend,
        "savings_rate": (income - total_spend) / income * 100 if income else 0.0,
        "tx_count": int(len(exp)), "avg_transaction": float(exp["spend"].mean()) if len(exp) else 0.0,
        "avg_daily_spend": total_spend / days, "days": days,
        "top_category": top_cat, "top_category_amount": float(by_cat.iloc[0]) if len(by_cat) else 0.0,
        "top_category_share": float(by_cat.iloc[0] / total_spend * 100) if total_spend else 0.0,
        "top_categories": by_cat.head(5),
        "biggest_expense": None if biggest is None else
        {"description": biggest["description"], "amount": float(biggest["spend"]),
         "date": biggest["tx_date"].strftime("%d %b %Y"), "category": biggest["category"]},
    }


def monthly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """One row per month: income, spend, savings, savings rate, month-on-month change."""
    if df.empty:
        return pd.DataFrame(columns=["month", "income", "spend", "savings", "savings_rate", "tx_count", "mom_change_pct"])
    spend = expenses(df).groupby("month")["spend"].agg(spend="sum", tx_count="count")
    income = incomes(df).groupby("month")["amount"].sum().rename("income")
    out = pd.concat([income, spend], axis=1).fillna(0.0).sort_index()
    out["savings"] = out["income"] - out["spend"]
    out["savings_rate"] = np.where(out["income"] > 0, out["savings"] / out["income"] * 100, 0.0)
    out["mom_change_pct"] = out["spend"].pct_change() * 100
    out["tx_count"] = out["tx_count"].astype(int)
    return out.reset_index().rename(columns={"index": "month"})


def category_summary(df: pd.DataFrame, month: str | None = None) -> pd.DataFrame:
    exp = expenses(filter_month(df, month))
    if exp.empty:
        return pd.DataFrame(columns=["category", "spend", "share_pct", "tx_count", "avg_tx", "max_tx"])
    g = exp.groupby("category")["spend"].agg(spend="sum", tx_count="count", avg_tx="mean", max_tx="max")
    g["share_pct"] = g["spend"] / g["spend"].sum() * 100
    return g.sort_values("spend", ascending=False).reset_index()[
        ["category", "spend", "share_pct", "tx_count", "avg_tx", "max_tx"]]


def payment_summary(df: pd.DataFrame, month: str | None = None) -> pd.DataFrame:
    exp = expenses(filter_month(df, month))
    if exp.empty:
        return pd.DataFrame(columns=["payment_method", "spend", "share_pct", "tx_count"])
    g = exp.groupby("payment_method")["spend"].agg(spend="sum", tx_count="count")
    g["share_pct"] = g["spend"] / g["spend"].sum() * 100
    return g.sort_values("spend", ascending=False).reset_index()[["payment_method", "spend", "share_pct", "tx_count"]]


def daily_spend(df: pd.DataFrame, month: str | None = None) -> pd.DataFrame:
    """Continuous daily series (zero-filled) with 7-day moving average and cumulative total."""
    exp = expenses(filter_month(df, month))
    if exp.empty:
        return pd.DataFrame(columns=["date", "spend", "ma7", "cumulative"])
    if month:
        start, end = month_bounds(month, df["tx_date"].max())
    else:
        start, end = exp["tx_date"].min().normalize(), exp["tx_date"].max().normalize()
    s = exp.groupby(exp["tx_date"].dt.normalize())["spend"].sum()
    s = s.reindex(pd.date_range(start, end, freq="D"), fill_value=0.0)
    out = pd.DataFrame({"date": s.index, "spend": s.values})
    out["ma7"] = out["spend"].rolling(7, min_periods=1).mean()
    out["cumulative"] = out["spend"].cumsum()
    return out


def weekday_category_matrix(df: pd.DataFrame, month: str | None = None) -> pd.DataFrame:
    exp = expenses(filter_month(df, month))
    if exp.empty:
        return pd.DataFrame()
    pv = exp.pivot_table(index="category", columns="weekday", values="spend", aggfunc="sum", fill_value=0.0)
    pv = pv.reindex(columns=WEEKDAYS, fill_value=0.0)
    return pv.loc[pv.sum(axis=1).sort_values(ascending=False).index]


def weekday_summary(df: pd.DataFrame, month: str | None = None) -> pd.DataFrame:
    """Average spend per calendar day for each weekday (so busy months do not distort it)."""
    d = daily_spend(df, month)
    if d.empty:
        return pd.DataFrame(columns=["weekday", "avg_spend"])
    d["weekday"] = d["date"].dt.dayofweek.map(dict(enumerate(WEEKDAYS)))
    return d.groupby("weekday")["spend"].mean().reindex(WEEKDAYS).rename("avg_spend").reset_index()


# ----------------------------------------------------------------------------
# Merchants, recurring payments, anomalies
# ----------------------------------------------------------------------------
_NOISE = re.compile(r"\b(upi|pos|ref|order|trip|txn|payment|ybl|okhdfcbank|oksbi|paytm|imps|neft)\b")


def merchant_name(description: str) -> str:
    """'UPI-SWIGGY-ORDER-#13887-1033@YBL' -> 'Swiggy'. Strips refs, digits and bank noise."""
    text = re.sub(r"@\w+", " ", str(description).lower())
    text = re.sub(r"[^a-z&\s.']", " ", text.replace("-", " "))
    text = _NOISE.sub(" ", text)
    words = [w for w in re.sub(r"\s+", " ", text).split() if len(w) > 1]
    return " ".join(words[:3]).title() or "Unknown"


def top_merchants(df: pd.DataFrame, month: str | None = None, n: int = 10) -> pd.DataFrame:
    exp = expenses(filter_month(df, month))
    if exp.empty:
        return pd.DataFrame(columns=["merchant", "spend", "tx_count", "avg_tx"])
    exp["merchant"] = exp["description"].map(merchant_name)
    g = exp.groupby("merchant")["spend"].agg(spend="sum", tx_count="count", avg_tx="mean")
    return g.sort_values("spend", ascending=False).head(n).reset_index()


def detect_recurring(df: pd.DataFrame, min_occurrences: int = 3) -> pd.DataFrame:
    """Find subscriptions / bills: same merchant, 3+ distinct months, roughly monthly spacing."""
    exp = expenses(df)
    cols = ["merchant", "category", "frequency", "avg_amount", "occurrences", "last_date",
            "next_expected", "annual_cost", "type"]
    if exp.empty:
        return pd.DataFrame(columns=cols)
    exp["merchant"] = exp["description"].map(merchant_name)
    rows = []
    for merchant, g in exp.groupby("merchant"):
        g = g.sort_values("tx_date")
        if len(g) < min_occurrences or g["month"].nunique() < min_occurrences:
            continue
        gaps = g["tx_date"].diff().dt.days.dropna()
        median_gap = float(gaps.median())
        regular = float(gaps.between(25, 35).mean())            # share of gaps that look "monthly"
        if not (25 <= median_gap <= 35 and regular >= 0.7 and g["month"].nunique() >= 0.8 * len(g)):
            continue
        cv = float(g["spend"].std(ddof=0) / g["spend"].mean()) if g["spend"].mean() else 0.0
        avg = float(g["spend"].mean())
        last = g["tx_date"].max()
        rows.append({"merchant": merchant, "category": g["category"].mode().iat[0], "frequency": "Monthly",
                     "avg_amount": avg, "occurrences": int(len(g)), "last_date": last.normalize(),
                     "next_expected": (last + pd.Timedelta(days=round(median_gap))).normalize(),
                     "annual_cost": avg * 12, "type": "Fixed" if cv < 0.1 else "Variable"})
    if not rows:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(rows).sort_values("annual_cost", ascending=False).reset_index(drop=True)[cols]


def detect_anomalies(df: pd.DataFrame, z_threshold: float = 3.5, min_history: int = 6,
                     min_multiple: float = 5.0) -> pd.DataFrame:
    """Flag unusually large expenses: robust z-score (median/MAD) AND at least `min_multiple` x the typical amount.

    Baseline = the merchant's own history when it has `min_history`+ transactions (a restaurant is judged
    against that restaurant), otherwise the category's one-off purchases.
    """
    exp = expenses(df)
    cols = ["tx_date", "description", "category", "spend", "typical", "times_typical", "score"]
    if exp.empty:
        return pd.DataFrame(columns=cols)
    exp["merchant"] = exp["description"].map(merchant_name)
    counts = exp["merchant"].map(exp["merchant"].value_counts())
    exp["regular"] = counts >= min_history
    flagged = []

    def scan(candidates: pd.DataFrame, baseline: pd.DataFrame) -> None:
        """Flag rows in `candidates` that are far above the baseline's median (robust z-score)."""
        if len(baseline) < min_history:
            return
        median = baseline["spend"].median()
        dev = (baseline["spend"] - median).abs()
        mad = dev.median()
        if mad > 0:
            score = 0.6745 * (candidates["spend"] - median) / mad
        elif dev.mean() > 0:                         # many identical amounts (e.g. a fixed gym fee): use mean abs. deviation
            score = (candidates["spend"] - median) / (1.2533 * dev.mean())
        else:
            return
        hit = candidates[(score > z_threshold) & (candidates["spend"] > min_multiple * median)].copy()
        if len(hit):
            hit["typical"], hit["score"] = median, score[hit.index]
            flagged.append(hit)

    for _, g in exp[exp["regular"]].groupby("merchant"):        # judged against their own history
        scan(g, g)
    for _, g in exp.groupby("category"):                         # one-off purchases vs the whole category
        scan(g[~g["regular"]], g)
    if not flagged:
        return pd.DataFrame(columns=cols)
    out = pd.concat(flagged)
    out["times_typical"] = out["spend"] / out["typical"]
    return out.sort_values("spend", ascending=False)[cols].reset_index(drop=True)


# ----------------------------------------------------------------------------
# Forecast
# ----------------------------------------------------------------------------
def forecast_next_month(df: pd.DataFrame, weights=(0.5, 0.3, 0.2)) -> dict:
    """Weighted moving average of the last 3 complete months, per category, plus a linear-trend check."""
    months = complete_months(df)
    exp = expenses(df)
    if len(months) < 2 or exp.empty:
        return {"next_month": None, "total": 0.0, "by_category": pd.DataFrame(columns=["category", "forecast"]),
                "trend_total": None}
    last = months[-min(3, len(months)):][::-1]                    # newest first
    w = np.array(weights[:len(last)], dtype=float)
    w = w / w.sum()
    pv = exp[exp["month"].isin(last)].pivot_table(index="category", columns="month", values="spend",
                                                  aggfunc="sum", fill_value=0.0)
    pv = pv.reindex(columns=last, fill_value=0.0)
    fc = (pv * w).sum(axis=1).sort_values(ascending=False).rename("forecast").reset_index()
    monthly = exp[exp["month"].isin(months)].groupby("month")["spend"].sum().sort_index()
    slope, intercept = np.polyfit(np.arange(len(monthly)), monthly.values, 1)
    return {"next_month": str(pd.Period(months[-1], "M") + 1), "total": float(fc["forecast"].sum()),
            "by_category": fc, "trend_total": float(max(slope * len(monthly) + intercept, 0)),
            "trend_slope": float(slope)}


# ----------------------------------------------------------------------------
# Financial health score
# ----------------------------------------------------------------------------
def financial_health_score(df: pd.DataFrame, month: str, budget_status: pd.DataFrame | None = None) -> dict:
    """0-100 score: savings rate (40) + budget discipline (30) + spend stability (15) + needs-vs-wants (15)."""
    m = filter_month(df, month)
    k = kpis(m, period_days(df, month))
    save_pts = float(np.clip(k["savings_rate"] / 20.0, 0, 1) * 40)               # 20%+ savings = full marks

    if budget_status is not None and len(budget_status):
        ok = (budget_status["spend"] <= budget_status["limit"]).mean()
        budget_pts = float(ok * 30)
    else:
        budget_pts = 15.0                                                         # neutral when no budgets set

    ms = monthly_summary(df)
    recent = ms[ms["month"] <= month].tail(6)["spend"]
    cv = recent.std(ddof=0) / recent.mean() if len(recent) >= 3 and recent.mean() else 0.25
    stability_pts = float(np.clip(1 - cv / 0.5, 0, 1) * 15)                        # CV 0 -> 15 pts, 0.5+ -> 0

    exp = expenses(m)
    wants_share = (exp.loc[~exp["category"].isin(config.ESSENTIAL_CATEGORIES), "spend"].sum() /
                   exp["spend"].sum()) if len(exp) and exp["spend"].sum() else 0.0
    wants_pts = float(np.clip(1 - max(wants_share - 0.30, 0) / 0.40, 0, 1) * 15)   # wants <= 30% -> full marks

    total = save_pts + budget_pts + stability_pts + wants_pts
    label = ("Excellent" if total >= 80 else "Good" if total >= 65 else "Fair" if total >= 45 else "Needs attention")
    return {"score": round(total), "label": label, "wants_share": wants_share * 100,
            "components": {"Savings rate (40)": round(save_pts, 1), "Budget discipline (30)": round(budget_pts, 1),
                           "Spend stability (15)": round(stability_pts, 1), "Needs vs wants (15)": round(wants_pts, 1)}}


# ----------------------------------------------------------------------------
# Human-readable insights
# ----------------------------------------------------------------------------
def generate_insights(df: pd.DataFrame, month: str, budget_status: pd.DataFrame | None = None) -> list[str]:
    """Plain-English findings - the 'storytelling' layer on top of the numbers."""
    out: list[str] = []
    m = filter_month(df, month)
    k = kpis(m, period_days(df, month))
    if k["total_spend"] == 0:
        return ["No expenses recorded for this period."]

    out.append(f"You spent {inr(k['total_spend'])} in {month_label(month)}; the biggest category was "
               f"{k['top_category']} at {inr(k['top_category_amount'])} ({k['top_category_share']:.0f}% of spend).")

    if k["income"] > 0:
        verb = "saved" if k["savings"] >= 0 else "overspent by"
        tag = ("above" if k["savings_rate"] >= 20 else "below") + " the 20% rule of thumb"
        out.append(f"You {verb} {inr(abs(k['savings']))} - a savings rate of {k['savings_rate']:.0f}%, {tag}."
                   if k["savings"] >= 0 else f"You {verb} {inr(abs(k['savings']))} this period - spend exceeded income.")

    out.append(f"Average daily spend was {inr(k['avg_daily_spend'])} across {k['days']} days.")

    ms = monthly_summary(df).set_index("month")
    if month in ms.index and not np.isnan(ms.loc[month, "mom_change_pct"]):
        ch = ms.loc[month, "mom_change_pct"]
        prev = str(pd.Period(month, "M") - 1)
        out.append(f"Spending {'rose' if ch > 0 else 'fell'} {abs(ch):.0f}% versus {month_label(prev)}.")
        cur_c = expenses(m).groupby("category")["spend"].sum()
        prv_c = expenses(filter_month(df, prev)).groupby("category")["spend"].sum()
        delta = (cur_c - prv_c.reindex(cur_c.index).fillna(0)).sort_values(ascending=False)
        if len(delta) and delta.iloc[0] > 0:
            out.append(f"Biggest increase vs last month: {delta.index[0]} (+{inr(delta.iloc[0])}).")

    wk = weekday_summary(df[df["category"] != "Rent & Housing"], month).dropna()   # rent day would distort it
    if len(wk):
        top = wk.loc[wk["avg_spend"].idxmax()]
        out.append(f"{top['weekday']} is your most expensive day of the week (average {inr(top['avg_spend'])}).")

    b = kpis(m[m["category"] != "Rent & Housing"])["biggest_expense"]         # rent is fixed, not interesting
    if b:
        out.append(f"Largest one-off expense: {inr(b['amount'])} on '{b['description']}' ({b['date']}).")

    if budget_status is not None and len(budget_status):
        over = budget_status[budget_status["status"] == "Over budget"]
        warn = budget_status[budget_status["status"] == "Warning"]
        if len(over):
            worst = over.sort_values("over_by", ascending=False).iloc[0]
            out.append(f"Over budget in {len(over)} categor{'y' if len(over) == 1 else 'ies'}; worst is "
                       f"{worst['category']} by {inr(worst['over_by'])}.")
        if len(warn):
            out.append("Close to the limit: " + ", ".join(warn["category"]) + ".")
        if not len(over) and not len(warn):
            out.append("All budgeted categories are within limits - well done.")

    rec = detect_recurring(df)
    if len(rec):
        out.append(f"{len(rec)} recurring payments detected costing about {inr(rec['annual_cost'].sum())} per year "
                   f"(largest: {rec.iloc[0]['merchant']}).")

    an = detect_anomalies(df)                                   # judged against full history ...
    an = an[an["tx_date"].dt.strftime("%Y-%m") == month]         # ... but reported for this month only
    if len(an):
        a = an.iloc[0]
        out.append(f"Unusual expense: {inr(a['spend'])} on '{a['description']}' is {a['times_typical']:.1f}x your "
                   f"typical {a['category']} transaction.")
    return out
