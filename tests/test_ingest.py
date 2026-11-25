import io
import math
import tempfile
from pathlib import Path

import pandas as pd

from src import ingest, models


def test_parse_amount_variants():
    p = ingest.parse_amount_value
    assert p("₹1,299.50") == 1299.5
    assert p("Rs.1,200") == 1200
    assert p("(500)") == -500
    assert p("250 Dr") == -250
    assert p("-45") == -45
    assert math.isnan(p("abc")) and math.isnan(p("")) and math.isnan(p(None))


def test_iso_dates_are_never_day_swapped():
    s = pd.Series(["2026-10-05", "05/10/26", "5 Oct 2026", "garbage"])
    out = ingest.parse_dates(s, dayfirst=True)
    assert out.iloc[0] == pd.Timestamp("2026-10-05")          # ISO stays year-first
    assert out.iloc[1] == pd.Timestamp("2026-10-05")          # dd/mm/yy
    assert out.iloc[2] == pd.Timestamp("2026-10-05")
    assert pd.isna(out.iloc[3])


def test_debit_credit_columns_and_cleaning():
    raw = pd.DataFrame({
        "Date": ["01/11/26", "02/11/26", "02/11/26", "bad", "03/11/26"],
        "Narration": ["  SALARY  ACME ", "UPI-SWIGGY-1@ybl", "UPI-SWIGGY-1@ybl", "x", "NO AMOUNT"],
        "Withdrawal Amt.": ["", "349.00", "349.00", "10", ""],
        "Deposit Amt.": ["50,000.00", "", "", "", ""],
    })
    df, rep = ingest.standardize(raw, account="HDFC")
    assert list(df["amount"]) == [50000.0, -349.0]
    assert df["description"].iloc[0] == "SALARY ACME"          # whitespace collapsed
    assert rep["duplicates_removed"] == 1 and rep["invalid_dates"] == 1 and rep["invalid_amounts"] == 1


def test_missing_columns_raise_helpful_error():
    try:
        ingest.standardize(pd.DataFrame({"foo": [1]}))
    except ValueError as exc:
        assert "required column" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_expenses_positive_flag_flips_sign():
    raw = pd.DataFrame({"Date": ["2026-01-01"], "Description": ["Coffee"], "Amount": ["120"]})
    df, _ = ingest.standardize(raw, expenses_positive=True)
    assert df["amount"].iloc[0] == -120


def test_reimport_is_idempotent_and_manual_entry():
    with tempfile.TemporaryDirectory() as d:
        db = Path(d) / "t.db"
        csv = io.StringIO("Date,Description,Amount,Payment Method\n2026-01-01,Swiggy Order #1,-300,gpay\n"
                          "2026-01-02,Salary,50000,neft\n")
        csv.name = "x.csv"
        first = ingest.import_csv(csv, db_path=db, account="A")
        assert first["inserted"] == 2
        csv.seek(0)
        second = ingest.import_csv(csv, db_path=db, account="A")
        assert second["inserted"] == 0 and second["skipped"] == 2
        assert ingest.add_manual_transaction("2026-01-05", "Chai", 20, "expense", db_path=db)
        assert not ingest.add_manual_transaction("2026-01-05", "Chai", 20, "expense", db_path=db)
        with models.connect(db) as con:
            pm = con.execute("SELECT payment_method FROM transactions WHERE description LIKE 'Swiggy%'").fetchone()[0]
            amt = con.execute("SELECT amount FROM transactions WHERE description='Chai'").fetchone()[0]
        assert pm == "UPI" and amt == -20
