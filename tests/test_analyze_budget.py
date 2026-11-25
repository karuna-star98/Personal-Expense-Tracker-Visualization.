import tempfile
from pathlib import Path

import pandas as pd

from src import analyze, budget, categorize, generate_data, ingest, models


def make_frame(rows):
    return analyze.prepare_frame(pd.DataFrame(rows, columns=["tx_date", "description", "amount", "category"]))


def test_kpis_and_monthly_summary():
    df = make_frame([("2026-01-01", "Salary", 1000, "Income"), ("2026-01-05", "Rent", -400, "Rent & Housing"),
                     ("2026-01-09", "Food", -100, "Food & Dining"), ("2026-02-02", "Food", -300, "Food & Dining")])
    k = analyze.kpis(analyze.filter_month(df, "2026-01"), days=31)
    assert k["total_spend"] == 500 and k["income"] == 1000 and k["savings"] == 500
    assert round(k["savings_rate"]) == 50 and k["top_category"] == "Rent & Housing"
    assert round(k["avg_daily_spend"], 4) == round(500 / 31, 4)
    ms = analyze.monthly_summary(df).set_index("month")
    assert ms.loc["2026-02", "spend"] == 300 and round(ms.loc["2026-02", "mom_change_pct"]) == -40


def test_complete_months_excludes_partial_last_month():
    df = make_frame([("2026-01-01", "a", -1, "x"), ("2026-01-31", "b", -1, "x"), ("2026-02-10", "c", -1, "x")])
    assert analyze.complete_months(df) == ["2026-01"] and analyze.default_month(df) == "2026-01"


def test_recurring_and_anomaly_detection():
    rows = [(f"2026-{m:02d}-05", "Netflix Subscription", -649, "Entertainment") for m in range(1, 7)]
    rows += [(f"2026-{m:02d}-{d:02d}", f"Cafe Coffee #{m}{d}", -200 - d, "Food & Dining") for m in range(1, 4) for d in (3, 11, 19)]
    rows += [("2026-03-20", "Fancy Dinner Special", -5000, "Food & Dining")]
    df = make_frame(rows)
    rec = analyze.detect_recurring(df)
    assert "Netflix Subscription" in set(rec["merchant"]) and rec.iloc[0]["type"] == "Fixed"
    an = analyze.detect_anomalies(df)
    assert "Fancy Dinner Special" in set(an["description"])


def test_budget_status_and_upsert():
    with tempfile.TemporaryDirectory() as d:
        db = Path(d) / "t.db"
        models.init_db(db)
        sample = generate_data.generate_transactions("2026-01-01", "2026-03-31", seed=1)
        df, _ = ingest.standardize(sample)
        ingest.upsert_transactions(df, db)
        categorize.run(db)
        budget.set_budget("2026-03", "Rent & Housing", 1000, db)
        budget.set_budget("2026-03", "Rent & Housing", 20000, db)            # update, not duplicate
        assert len(budget.get_budgets("2026-03", db)) == 1
        budget.set_budget("2026-03", "Groceries", 1, db)
        st = budget.check_budget("2026-03", db).set_index("category")
        assert st.loc["Rent & Housing", "status"] in ("On track", "Warning")
        assert st.loc["Groceries", "status"] == "Over budget" and st.loc["Groceries", "over_by"] > 0
        assert any("Groceries" in a for a in budget.budget_alerts(st.reset_index()))


def test_forecast_and_health_score_ranges():
    sample = generate_data.generate_transactions("2025-11-01", "2026-05-05", seed=3)
    df = analyze.prepare_frame(ingest.standardize(sample)[0].assign(category=lambda d: d["description"].map(categorize.classify)))
    fc = analyze.forecast_next_month(df)
    assert fc["next_month"] == "2026-05" and fc["total"] > 0
    h = analyze.financial_health_score(df, "2026-04")
    assert 0 <= h["score"] <= 100 and sum(h["components"].values()) > 0


def test_inr_formatting():
    from src.config import inr
    assert inr(1234567) == "₹12,34,567" and inr(999) == "₹999" and inr(-5000.5, 1) == "-₹5,000.5"
