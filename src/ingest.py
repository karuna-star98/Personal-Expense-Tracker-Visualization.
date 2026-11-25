"""CSV ingestion: auto-detect columns, clean, standardise and load into SQLite."""
from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

from . import models

STANDARD_COLS = ["tx_date", "description", "amount", "account", "payment_method", "category", "raw_source"]

# Banks name columns differently - we match on lower-cased header aliases
COLUMN_ALIASES = {
    "date": ["date", "txn date", "transaction date", "tx_date", "posting date", "value date", "value dt", "txn_date"],
    "description": ["description", "narration", "details", "particulars", "transaction details",
                    "remarks", "note", "notes", "merchant"],
    "amount": ["amount", "amt", "transaction amount", "amount (inr)"],
    "debit": ["withdrawal amt.", "withdrawal amt", "withdrawal", "withdrawals", "debit", "debit amount", "dr"],
    "credit": ["deposit amt.", "deposit amt", "deposit", "deposits", "credit", "credit amount", "cr"],
    "payment_method": ["payment method", "payment_method", "payment mode", "payment type", "mode", "method"],
    "category": ["category", "expense category"],
    "account": ["account", "account name", "bank"],
}

CATEGORY_ALIASES = {
    "food": "Food & Dining", "dining": "Food & Dining", "eating out": "Food & Dining",
    "food and dining": "Food & Dining", "restaurants": "Food & Dining",
    "grocery": "Groceries", "groceries": "Groceries",
    "transportation": "Transport", "travel local": "Transport", "commute": "Transport",
    "utilities": "Bills & Utilities", "bills": "Bills & Utilities", "bills and utilities": "Bills & Utilities",
    "rent": "Rent & Housing", "housing": "Rent & Housing", "rent and housing": "Rent & Housing",
    "health": "Health & Fitness", "medical": "Health & Fitness", "fitness": "Health & Fitness",
    "health and fitness": "Health & Fitness",
    "shopping": "Shopping", "entertainment": "Entertainment", "education": "Education",
    "travel": "Travel", "income": "Income", "salary": "Income",
    "transfers": "Personal Transfers", "personal transfers": "Personal Transfers",
}

PAYMENT_ALIASES = {
    "upi": "UPI", "gpay": "UPI", "google pay": "UPI", "phonepe": "UPI", "paytm": "UPI", "bhim": "UPI",
    "credit card": "Credit Card", "credit": "Credit Card", "cc": "Credit Card", "creditcard": "Credit Card",
    "debit card": "Debit Card", "debit": "Debit Card", "dc": "Debit Card", "debitcard": "Debit Card",
    "cash": "Cash",
    "net banking": "Net Banking", "netbanking": "Net Banking", "neft": "Net Banking", "imps": "Net Banking",
    "rtgs": "Net Banking", "online": "Net Banking", "bank transfer": "Net Banking",
}


# ----------------------------------------------------------------------------
# Small parsing helpers
# ----------------------------------------------------------------------------
def detect_columns(columns) -> dict[str, str]:
    """Map our standard field names to the actual CSV headers (case-insensitive)."""
    lookup = {str(c).strip().lower(): c for c in columns}
    found: dict[str, str] = {}
    for field, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in lookup:
                found[field] = lookup[alias]
                break
    return found


def parse_amount_value(value) -> float:
    """'₹1,299.50' -> 1299.5 ; '(500)' -> -500 ; '250 Dr' -> -250 ; junk -> NaN."""
    if value is None:
        return np.nan
    if isinstance(value, (int, float, np.number)):
        return np.nan if (isinstance(value, float) and math.isnan(value)) else float(value)
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "-", "--", "null"}:
        return np.nan
    low = text.lower()
    negative = (text.startswith("(") and text.endswith(")")) or bool(re.search(r"\bdr\.?$", low))
    text = re.sub(r"(?i)\b(rs|inr)\.?", "", text).replace("₹", "")
    text = re.sub(r"[^\d.\-]", "", text)
    if text in {"", "-", ".", "-."}:
        return np.nan
    try:
        number = float(text)
    except ValueError:
        return np.nan
    return -abs(number) if negative else number


def parse_amounts(series: pd.Series) -> pd.Series:
    return series.map(parse_amount_value).astype(float)


def parse_dates(series: pd.Series, dayfirst: bool = True) -> pd.Series:
    """Parse mixed date formats (2026-10-05, 05/10/26, 5 Oct 2026) -> datetime64 (NaT if invalid).

    ISO dates (YYYY-MM-DD) are always read year-first; only ambiguous dd/mm vs mm/dd
    strings use `dayfirst`.  (pandas would otherwise swap day and month for ISO strings.)
    """
    text = series.astype("string").str.strip()
    iso = text.str.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}").fillna(False).astype(bool)
    out = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
    if iso.any():
        out[iso] = pd.to_datetime(text[iso], errors="coerce", dayfirst=False, format="mixed")
    if (~iso).any():
        out[~iso] = pd.to_datetime(text[~iso], errors="coerce", dayfirst=dayfirst, format="mixed")
    return out


def normalize_payment_method(value, description: str = "") -> str:
    key = re.sub(r"\s+", " ", str(value or "")).strip().lower()
    if key in PAYMENT_ALIASES:
        return PAYMENT_ALIASES[key]
    d = str(description).lower()
    if re.search(r"\b(salary|payroll|payout)\b", d):
        return "Net Banking"
    if re.search(r"\bupi\b", d):
        return "UPI"
    if re.search(r"\b(atm|cash wdl|cash)\b", d):
        return "Cash"
    if re.search(r"\b(pos|debit card)\b", d):
        return "Debit Card"
    if re.search(r"\b(neft|imps|rtgs|netbanking|net banking)\b", d):
        return "Net Banking"
    if re.search(r"credit card|cc payment", d):
        return "Credit Card"
    return "Other"


def normalize_category(value) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text or text.lower() in {"nan", "none"}:
        return ""
    key = text.lower().replace("&", "and")
    return CATEGORY_ALIASES.get(key, text.title() if text.islower() else text)


def clean_description(value) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()


# ----------------------------------------------------------------------------
# Main reader / cleaner
# ----------------------------------------------------------------------------
def standardize(df: pd.DataFrame, account: str | None = None, mapping: dict | None = None,
                dayfirst: bool = True, expenses_positive: bool = False,
                source: str = "", default_method: str | None = None) -> tuple[pd.DataFrame, dict]:
    """Convert any transactions table into the standard schema and report what was cleaned."""
    report = {"rows_read": len(df)}
    cols = {**detect_columns(df.columns), **(mapping or {})}
    missing = [f for f in ("date", "description") if f not in cols]
    if "amount" not in cols and not ({"debit", "credit"} & set(cols)):
        missing.append("amount (or debit/credit)")
    if missing:
        raise ValueError(f"Could not find required column(s): {', '.join(missing)}. "
                         f"Headers found: {list(df.columns)}")

    out = pd.DataFrame(index=df.index)
    out["tx_date"] = parse_dates(df[cols["date"]], dayfirst=dayfirst)
    out["description"] = df[cols["description"]].map(clean_description)

    # Amount: single signed column, or separate debit/credit columns
    if "amount" in cols:
        amount = parse_amounts(df[cols["amount"]])
        if expenses_positive:
            amount = -amount
    else:
        debit = parse_amounts(df[cols["debit"]]).abs() if "debit" in cols else pd.Series(np.nan, index=df.index)
        credit = parse_amounts(df[cols["credit"]]).abs() if "credit" in cols else pd.Series(np.nan, index=df.index)
        amount = credit.fillna(0) - debit.fillna(0)
        amount[debit.isna() & credit.isna()] = np.nan
    out["amount"] = amount

    acc_col = cols.get("account")
    out["account"] = df[acc_col].astype(str).str.strip() if acc_col else (account or "Manual")
    if account and acc_col:
        out.loc[out["account"].isin(["", "nan"]), "account"] = account

    pm_col = cols.get("payment_method")
    raw_pm = df[pm_col] if pm_col else pd.Series([default_method or ""] * len(df), index=df.index)
    out["payment_method"] = [normalize_payment_method(p, d) for p, d in zip(raw_pm, out["description"])]

    cat_col = cols.get("category")
    out["category"] = df[cat_col].map(normalize_category) if cat_col else ""
    out["raw_source"] = source

    # ---- cleaning steps (each one is counted for the report) ----
    bad_date = out["tx_date"].isna()
    bad_desc = out["description"].str.strip().eq("") | out["description"].str.lower().eq("nan")
    bad_amt = out["amount"].isna()
    zero = out["amount"].fillna(1).eq(0)
    invalid = bad_date | bad_amt | bad_desc | zero
    report.update(invalid_dates=int(bad_date.sum()), invalid_amounts=int(bad_amt.sum()),
                  empty_descriptions=int((bad_desc & ~bad_date & ~bad_amt).sum()), zero_amounts=int(zero.sum()),
                  dropped_invalid=int(invalid.sum()))
    out = out[~invalid].copy()

    out["tx_date"] = out["tx_date"].dt.strftime("%Y-%m-%d")
    before = len(out)
    out = out.drop_duplicates(subset=["tx_date", "description", "amount", "account"], keep="first")
    report["duplicates_removed"] = before - len(out)

    out = out.sort_values("tx_date").reset_index(drop=True)[STANDARD_COLS]
    report["rows_clean"] = len(out)
    return out, report


def read_transactions_csv(source, account: str | None = None, **kwargs) -> tuple[pd.DataFrame, dict]:
    """Read a CSV path / uploaded file object and return (clean_df, cleaning_report)."""
    df = pd.read_csv(source, sep=kwargs.pop("sep", None), engine="python", dtype=str, skip_blank_lines=True)
    df = df.dropna(how="all")
    name = getattr(source, "name", None) or str(source)
    return standardize(df, account=account, source=Path(name).name, **kwargs)


def read_bank_csv(path, account, date_col=None, desc_col=None, amt_col=None, **kwargs):
    """Backward-compatible helper: explicit column names for unusual bank exports."""
    mapping = {k: v for k, v in (("date", date_col), ("description", desc_col), ("amount", amt_col)) if v}
    return read_transactions_csv(path, account=account, mapping=mapping, **kwargs)


# ----------------------------------------------------------------------------
# Database loading
# ----------------------------------------------------------------------------
def upsert_transactions(df: pd.DataFrame, db_path=None) -> dict:
    """INSERT OR IGNORE rows. The UNIQUE constraint makes re-importing the same file safe."""
    if df.empty:
        return {"inserted": 0, "skipped": 0}
    models.init_db(db_path)
    with models.connect(db_path) as con:
        cats = models.category_map(con, create_missing=[c for c in df["category"].unique() if c])
        rows = []
        for r in df.itertuples(index=False):
            cat_id = cats.get(r.category) if r.category else None
            rows.append((r.tx_date, r.description, float(r.amount), r.account, r.payment_method,
                         cat_id, "csv" if cat_id else None, r.raw_source))
        before = con.total_changes
        con.executemany(
            """INSERT OR IGNORE INTO transactions
               (tx_date, description, amount, account, payment_method, category_id, category_source, raw_source)
               VALUES (?,?,?,?,?,?,?,?)""", rows)
        inserted = con.total_changes - before
    return {"inserted": inserted, "skipped": len(rows) - inserted}


def import_csv(source, db_path=None, **kwargs) -> dict:
    """Read + clean + load in one call. Returns the cleaning report plus insert counts."""
    df, report = read_transactions_csv(source, **kwargs)
    report.update(upsert_transactions(df, db_path))
    return report


def add_manual_transaction(date, description: str, amount: float, kind: str = "expense",
                           category: str | None = None, payment_method: str = "UPI",
                           account: str = "Manual", db_path=None) -> bool:
    """Insert one manually-entered transaction. `amount` is positive; `kind` decides the sign."""
    if amount is None or float(amount) <= 0:
        raise ValueError("Amount must be greater than zero.")
    signed = -abs(float(amount)) if kind.lower() == "expense" else abs(float(amount))
    row = pd.DataFrame([{
        "tx_date": pd.Timestamp(date).strftime("%Y-%m-%d"),
        "description": clean_description(description) or "Manual entry",
        "amount": signed, "account": account or "Manual",
        "payment_method": normalize_payment_method(payment_method),
        "category": normalize_category("Income" if kind.lower() == "income" and not category else category),
        "raw_source": "manual"}])
    result = upsert_transactions(row, db_path)
    if result["inserted"] and row.loc[0, "category"]:
        with models.connect(db_path) as con:     # mark as manually labelled
            con.execute("UPDATE transactions SET category_source='manual' WHERE raw_source='manual' "
                        "AND category_source='csv'")
    return bool(result["inserted"])
