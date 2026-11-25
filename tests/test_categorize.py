import tempfile
from pathlib import Path

import pandas as pd

from src import categorize, ingest, models


def test_rule_priority_and_normalisation():
    c = categorize.classify
    assert c("Swiggy Instamart #123", -1) == "Groceries"          # before Food
    assert c("Swiggy Order #123", -1) == "Food & Dining"
    assert c("Amazon Prime Annual", -1) == "Entertainment"        # before Shopping
    assert c("Amazon.in Order", -1) == "Shopping"
    assert c("UPI-ZOMATO-9876@YBL", -1) == "Food & Dining"       # bank-style narration
    assert c("RedBus ticket", -1) == "Travel"
    assert c("Cola Corner", -1) == "Uncategorized"                # 'ola' must not match inside 'cola'
    assert c("Anything", 500) == "Income"


def test_run_respects_existing_labels_and_manual_override():
    with tempfile.TemporaryDirectory() as d:
        db = Path(d) / "t.db"
        df = pd.DataFrame([
            {"tx_date": "2026-01-01", "description": "Swiggy Order #1", "amount": -200, "account": "A",
             "payment_method": "UPI", "category": "", "raw_source": "t"},
            {"tx_date": "2026-01-02", "description": "Swiggy Order #2", "amount": -250, "account": "A",
             "payment_method": "UPI", "category": "Shopping", "raw_source": "t"},     # user label wins
        ])
        ingest.upsert_transactions(df, db)
        categorize.run(db)
        with models.connect(db) as con:
            rows = dict(con.execute("SELECT t.description, c.name FROM transactions t JOIN categories c "
                                    "ON c.id=t.category_id").fetchall())
        assert rows["Swiggy Order #1"] == "Food & Dining" and rows["Swiggy Order #2"] == "Shopping"
        categorize.set_category(1, "Groceries", db)
        categorize.run(db, recategorize=True)                       # must not undo the manual label
        with models.connect(db) as con:
            name = con.execute("SELECT c.name FROM transactions t JOIN categories c ON c.id=t.category_id "
                               "WHERE t.id=1").fetchone()[0]
        assert name == "Groceries"
