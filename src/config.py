"""Central configuration: paths, categories, colours and money formatting."""
from __future__ import annotations

import os
import re
from pathlib import Path

# ----------------------------------------------------------------------------
# Paths (everything is relative to the project root, so it runs anywhere)
# ----------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_PATH = Path(os.getenv("EXPENSE_DB", ROOT / "db" / "expenses.db"))
OUTPUT_DIR = ROOT / "outputs"
CHART_DIR = OUTPUT_DIR / "charts"
REPORT_DIR = ROOT / "reports"
IMAGES_DIR = ROOT / "images"

SAMPLE_CSV = DATA_DIR / "sample_expenses.csv"
BANK_CSV = DATA_DIR / "hdfc_statement_nov2026.csv"

CURRENCY = "INR"
CURRENCY_SYMBOL = "₹"

# ----------------------------------------------------------------------------
# Categories: kind, colour used in every chart, and whether it is an "essential"
# ----------------------------------------------------------------------------
CATEGORY_META = {
    "Rent & Housing":     {"kind": "expense", "color": "#4F46E5", "essential": True},
    "Groceries":          {"kind": "expense", "color": "#10B981", "essential": True},
    "Bills & Utilities":  {"kind": "expense", "color": "#06B6D4", "essential": True},
    "Transport":          {"kind": "expense", "color": "#F59E0B", "essential": True},
    "Health & Fitness":   {"kind": "expense", "color": "#EF4444", "essential": True},
    "Education":          {"kind": "expense", "color": "#8B5CF6", "essential": True},
    "Food & Dining":      {"kind": "expense", "color": "#F97316", "essential": False},
    "Shopping":           {"kind": "expense", "color": "#EC4899", "essential": False},
    "Entertainment":      {"kind": "expense", "color": "#14B8A6", "essential": False},
    "Travel":             {"kind": "expense", "color": "#0EA5E9", "essential": False},
    "Personal Transfers": {"kind": "expense", "color": "#84CC16", "essential": False},
    "Uncategorized":      {"kind": "expense", "color": "#94A3B8", "essential": False},
    "Income":             {"kind": "income",  "color": "#22C55E", "essential": False},
}
EXPENSE_CATEGORIES = [c for c, m in CATEGORY_META.items() if m["kind"] == "expense"]
ESSENTIAL_CATEGORIES = [c for c, m in CATEGORY_META.items() if m["essential"]]
CATEGORY_COLORS = {c: m["color"] for c, m in CATEGORY_META.items()}

PAYMENT_METHODS = ["UPI", "Credit Card", "Debit Card", "Cash", "Net Banking", "Other"]
PAYMENT_COLORS = {
    "UPI": "#4F46E5", "Credit Card": "#EC4899", "Debit Card": "#06B6D4",
    "Cash": "#F59E0B", "Net Banking": "#10B981", "Other": "#94A3B8",
}

# Default monthly budget (INR) used for the demo; users can edit in the dashboard
DEFAULT_MONTHLY_BUDGET = {
    "Rent & Housing": 15200, "Groceries": 3500, "Food & Dining": 6500,
    "Transport": 4000, "Bills & Utilities": 3000, "Shopping": 5000,
    "Entertainment": 1800, "Health & Fitness": 3000, "Education": 1000,
    "Travel": 3000, "Personal Transfers": 1500,
}


# ----------------------------------------------------------------------------
# Money formatting with Indian digit grouping (1,23,456)
# ----------------------------------------------------------------------------
def inr(value: float, decimals: int = 0, symbol: bool = True) -> str:
    """Format a number as Indian Rupees, e.g. 123456.5 -> ₹1,23,457."""
    if value is None or value != value:  # None or NaN
        return "-"
    negative = value < 0
    whole, _, frac = f"{abs(value):.{decimals}f}".partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        head = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", head)
        whole = f"{head},{tail}"
    text = whole + (f".{frac}" if frac else "")
    return f"{'-' if negative else ''}{CURRENCY_SYMBOL if symbol else ''}{text}"


def ensure_dirs() -> None:
    for d in (DATA_DIR, DB_PATH.parent, OUTPUT_DIR, CHART_DIR, REPORT_DIR, IMAGES_DIR):
        d.mkdir(parents=True, exist_ok=True)
