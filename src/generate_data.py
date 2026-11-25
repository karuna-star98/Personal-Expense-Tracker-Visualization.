"""Synthetic (but realistic) Indian personal-finance data generator.

Why synthetic?  Real bank data is private.  This generator simulates one person's
12 months of life: salary, rent, UPI food orders, petrol, subscriptions, festive
shopping, a holiday, a few unusual big purchases (to test anomaly detection) and
messy bank-statement formatting (to test the cleaning pipeline).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config

START_DATE = "2025-11-01"
END_DATE = "2026-10-31"          # 12 full months -> Nov 2025 .. Oct 2026
BANK_START, BANK_END = "2026-11-01", "2026-11-22"   # month-to-date bank statement

ACCOUNT_FOR_METHOD = {
    "UPI": ["HDFC Savings", "HDFC Savings", "SBI Savings"],
    "Credit Card": ["ICICI Credit Card"],
    "Debit Card": ["HDFC Savings"],
    "Cash": ["Cash Wallet"],
    "Net Banking": ["HDFC Savings"],
}

# category -> payment-method probabilities
METHOD_WEIGHTS = {
    "Food & Dining":      {"UPI": .50, "Credit Card": .30, "Cash": .10, "Debit Card": .10},
    "Groceries":          {"UPI": .50, "Debit Card": .20, "Credit Card": .20, "Cash": .10},
    "Transport":          {"UPI": .60, "Cash": .20, "Credit Card": .20},
    "Shopping":           {"Credit Card": .60, "UPI": .20, "Net Banking": .20},
    "Entertainment":      {"Credit Card": .50, "UPI": .50},
    "Health & Fitness":   {"UPI": .60, "Debit Card": .20, "Cash": .20},
    "Travel":             {"Credit Card": .50, "Net Banking": .30, "UPI": .20},
    "Education":          {"Credit Card": .60, "UPI": .40},
    "Personal Transfers": {"UPI": 1.0},
}

FOOD = [("Swiggy Order", 150, 650), ("Zomato Order", 150, 700), ("Domino's Pizza", 250, 700),
        ("Starbucks Coffee", 250, 550), ("Cafe Coffee Day", 120, 380), ("Barbeque Nation Restaurant", 900, 2200),
        ("Haldiram's Restaurant", 200, 600), ("Local Chai Tapri", 20, 80), ("McDonald's", 180, 520)]
FOOD_WEIGHTS = [0.18, 0.18, 0.12, 0.10, 0.08, 0.02, 0.10, 0.14, 0.08]   # fine-dining is rare
GROCERY = [("BigBasket Grocery", 350, 2400), ("Blinkit Grocery", 150, 900), ("D-Mart Supermart", 600, 3200),
           ("Reliance Fresh", 250, 1500), ("Zepto Grocery", 150, 800), ("Sai Kirana General Store", 80, 450)]
TRANSPORT = [("Uber Trip", 90, 450), ("Ola Cabs", 80, 380), ("Rapido Bike Taxi", 40, 160)]
PETROL = [("Indian Oil Petrol Pump", 500, 1200), ("HP Petrol Pump", 500, 1100)]
SHOPPING = [("Amazon.in Order", 299, 3500), ("Flipkart Order", 299, 3200), ("Myntra Fashion", 599, 3500),
            ("Ajio Fashion", 499, 2500), ("Decathlon Sports", 400, 3000), ("Croma Electronics", 500, 3500)]
MOVIES = [("BookMyShow Movie Tickets", 300, 900), ("PVR Cinemas", 300, 800)]
PHARMACY = [("Apollo Pharmacy", 120, 900), ("MedPlus Pharmacy", 100, 700), ("Dr. Mehta Clinic Consultation", 400, 800)]
UNKNOWN = ["Shree Traders", "MH12 Services", "Om Sai Enterprises"]


def _pick_method(rng: np.random.Generator, category: str) -> str:
    weights = METHOD_WEIGHTS[category]
    return str(rng.choice(list(weights), p=np.array(list(weights.values())) / sum(weights.values())))


def generate_transactions(start: str = START_DATE, end: str = END_DATE, seed: int = 42) -> pd.DataFrame:
    """Return a DataFrame with Date, Description, Amount, Payment Method, Account, Category."""
    rng = np.random.default_rng(seed)
    rows: list[dict] = []

    def add(date, desc, amount, method, account=None, category=""):
        account = account or str(rng.choice(ACCOUNT_FOR_METHOD.get(method, ["HDFC Savings"])))
        rows.append({"Date": pd.Timestamp(date).date().isoformat(), "Description": desc,
                     "Amount": round(float(amount), 2), "Payment Method": method,
                     "Account": account, "Category": category})

    def ref() -> int:
        return int(rng.integers(10000, 99999))

    def variable(category, catalog, date, mult=1.0, weights=None):
        name, lo, hi = catalog[int(rng.choice(len(catalog), p=weights))]
        # right-skewed amounts: most small, a few large
        amt = lo + (hi - lo) * rng.beta(1.6, 3.2)
        method = _pick_method(rng, category)
        add(date, f"{name} #{ref()}", -round(amt * mult, 0), method)

    for day in pd.date_range(start, end, freq="D"):
        dom, month, weekend = day.day, day.month, day.dayofweek >= 5
        festive = 1.35 if month in (10, 11, 1) else 1.0        # Diwali / New-year sales
        summer = 1.6 if month in (4, 5, 6) else 1.0             # electricity (AC) in summer

        # ---------------- income ----------------
        if dom == 1:
            add(day, "SALARY - TECHNOVA SOLUTIONS PVT LTD", 55000, "Net Banking", "HDFC Savings")
        if dom == 20 and month in (12, 2, 5, 8, 10):
            add(day, f"Freelance Payout - Client {ref() % 90}", float(rng.integers(8, 16) * 1000), "UPI", "HDFC Savings")
        if rng.random() < 0.012:
            add(day, f"Amazon Refund #{ref()}", float(rng.integers(3, 20) * 100), "Net Banking", "HDFC Savings")

        # ---------------- fixed monthly bills ----------------
        if dom == 2:
            add(day, "Rent - Flat 302 (Landlord R. Patil)", -14000, "UPI", "HDFC Savings", "Rent & Housing")
        if dom == 3:
            add(day, "Society Maintenance Charges", -1200, "UPI", "HDFC Savings", "Rent & Housing")
        if dom == 5:
            add(day, "ACT Fibernet Broadband WiFi", -999, "Net Banking", "HDFC Savings")
        if dom == 7:
            add(day, "Cult.fit Gym Membership", -1500, "UPI", "HDFC Savings")
        if dom == 10:
            add(day, "Jio Prepaid Mobile Recharge", -349, "UPI", "HDFC Savings")
        if dom == 12:
            add(day, "Netflix Subscription", -649, "Credit Card", "ICICI Credit Card")
        if dom == 15:
            add(day, "Spotify Premium", -119, "Credit Card", "ICICI Credit Card")
        if dom == 18:
            add(day, f"MSEDCL Electricity Bill {month:02d}", -round(float(rng.integers(900, 1500)) * summer, 0),
                "Net Banking", "HDFC Savings")

        # ---------------- daily / random spending ----------------
        n_food = rng.poisson(0.85 if weekend else 0.5)
        for _ in range(n_food):
            variable("Food & Dining", FOOD, day, mult=1.25 if weekend else 1.0, weights=FOOD_WEIGHTS)
        if rng.random() < 0.17:
            variable("Groceries", GROCERY, day)
        if rng.random() < (0.28 if not weekend else 0.2):
            variable("Transport", TRANSPORT, day)
        if rng.random() < 0.075:
            variable("Transport", PETROL, day)
        if rng.random() < 0.07 * festive:
            variable("Shopping", SHOPPING, day, mult=festive)
        if rng.random() < (0.07 if weekend else 0.02):
            variable("Entertainment", MOVIES, day)
        if rng.random() < 0.035:
            variable("Health & Fitness", PHARMACY, day)
        if rng.random() < 0.035:
            name = ["Rohan", "Priya", "Amit", "Sneha"][int(rng.integers(4))]
            add(day, f"UPI P2P Transfer to {name} #{ref()}", -float(rng.integers(2, 12) * 100), "UPI",
                "HDFC Savings")
        if rng.random() < 0.006:     # merchants the rules cannot recognise
            add(day, f"{UNKNOWN[int(rng.integers(len(UNKNOWN)))]} #{ref()}", -float(rng.integers(2, 12) * 100),
                "UPI", "HDFC Savings")

    df = pd.DataFrame(rows)

    # ---------------- one-off events ----------------
    special = [
        ("2025-11-14", "IRCTC Train Ticket Home (Diwali)", -1240, "Net Banking", "HDFC Savings", ""),
        ("2025-11-24", "IRCTC Train Ticket Return", -1240, "Net Banking", "HDFC Savings", ""),
        ("2026-01-26", "Amazon.in - Noise-Cancelling Headphones", -18999, "Credit Card", "ICICI Credit Card", ""),
        ("2026-02-11", "Amazon Prime Annual Membership", -1499, "Credit Card", "ICICI Credit Card", ""),
        ("2026-03-20", "MakeMyTrip Goa Hotel Booking", -9800, "Credit Card", "ICICI Credit Card", ""),
        ("2026-03-21", "IndiGo Flight Pune-Goa", -5600, "Credit Card", "ICICI Credit Card", ""),
        ("2026-03-24", "IndiGo Flight Goa-Pune", -4900, "Credit Card", "ICICI Credit Card", ""),
        ("2026-04-09", "Udemy Course - Python for Data Science", -649, "Credit Card", "ICICI Credit Card", ""),
        ("2026-06-17", "Apollo Hospitals - Procedure Bill", -14500, "Debit Card", "HDFC Savings", ""),
        ("2026-08-08", "Coursera Plus Annual", -3400, "Credit Card", "ICICI Credit Card", ""),
        ("2026-09-14", "Shree Traders - Study Table", -4500, "UPI", "HDFC Savings", "Shopping"),  # user-labelled
        ("2026-10-28", "Amazon.in - Festive Sale Smart Watch", -7999, "Credit Card", "ICICI Credit Card", ""),
    ]
    lo, hi = pd.Timestamp(start), pd.Timestamp(end)
    extra = [dict(zip(df.columns, [d, desc, amt, m, a, c])) for d, desc, amt, m, a, c in special
             if lo <= pd.Timestamp(d) <= hi]
    if extra:
        df = pd.concat([df, pd.DataFrame(extra)], ignore_index=True)

    df = df.sort_values(["Date", "Description"]).reset_index(drop=True)
    return df


def generate_bank_statement(start: str = BANK_START, end: str = BANK_END, seed: int = 7) -> pd.DataFrame:
    """Create a *messy* HDFC-style statement (different headers, dd/mm/yy dates, split debit/credit)."""
    base = generate_transactions(start, end, seed)
    base = base[base["Account"] == "HDFC Savings"].reset_index(drop=True)
    rng = np.random.default_rng(seed)

    out, balance = [], 84250.0
    for _, r in base.iterrows():
        amt = float(r["Amount"])
        balance += amt
        d = pd.Timestamp(r["Date"])
        desc = str(r["Description"]).upper()
        if amt < 0 and r["Payment Method"] == "UPI":
            narration = f"UPI-{desc.replace(' ', '-')[:28]}-{int(rng.integers(10**9, 10**10))}@YBL"
        else:
            narration = f"  {desc}   "     # stray spaces, as in real exports
        out.append({
            "Date": d.strftime("%d/%m/%y"), "Narration": narration,
            "Chq./Ref.No.": f"{int(rng.integers(10**11, 10**12))}", "Value Dt": d.strftime("%d/%m/%y"),
            "Withdrawal Amt.": f"{-amt:,.2f}" if amt < 0 else "",
            "Deposit Amt.": f"{amt:,.2f}" if amt > 0 else "",
            "Closing Balance": f"{balance:,.2f}",
        })
    stmt = pd.DataFrame(out)

    # inject realistic dirt: an exact duplicate row, a blank-amount row and a junk footer row
    if len(stmt) > 6:
        stmt = pd.concat([stmt.iloc[:5], stmt.iloc[[4]], stmt.iloc[5:]], ignore_index=True)
        stmt.loc[len(stmt)] = ["23/11/26", "ATM CASH WDL (pending)", "", "23/11/26", "", "", ""]
        stmt.loc[len(stmt)] = ["", "*** END OF STATEMENT ***", "", "", "", "", ""]
    return stmt


def write_sample_files(data_dir=None, seed: int = 42) -> dict:
    """Write sample_expenses.csv and the bank statement CSV into data/."""
    config.ensure_dirs()
    data_dir = data_dir or config.DATA_DIR
    from pathlib import Path
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    tx = generate_transactions(seed=seed)
    stmt = generate_bank_statement()
    p1, p2 = data_dir / config.SAMPLE_CSV.name, data_dir / config.BANK_CSV.name
    tx.to_csv(p1, index=False)
    stmt.to_csv(p2, index=False)
    return {"sample": p1, "bank": p2, "rows_sample": len(tx), "rows_bank": len(stmt)}


if __name__ == "__main__":
    print(write_sample_files())
