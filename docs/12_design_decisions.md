# 12. Design decisions and data dictionary

## Column dictionary (`transactions`)
| Column | Meaning |
|---|---|
| `tx_date` | ISO date `YYYY-MM-DD` (text, sorts correctly) |
| `description` | cleaned merchant/narration text |
| `amount` | signed rupees: **expense < 0, income > 0** |
| `account` | e.g. HDFC Savings, ICICI Credit Card, Cash Wallet |
| `payment_method` | UPI, Credit Card, Debit Card, Cash, Net Banking, Other |
| `category_id` / `category_source` | FK to `categories`; `csv`, `rule`, `ml` or `manual` |
| `raw_source` | file the row came from (audit trail) |

## Why these rules?
- **First rule wins**, so specific patterns come first (Instamart before Swiggy, Prime before Amazon).
- Text is normalised (lower-case, punctuation → space) and patterns use word boundaries, so `ola` never matches `cola`.
- **Dates:** ISO strings are always year-first; only ambiguous `dd/mm` vs `mm/dd` strings follow the `dayfirst` option.
- **Health score:** savings rate 40 pts (20% saves = full), budget discipline 30, spend stability 15 (low month-to-month variation), needs-vs-wants 15 (wants ≤30% of spend).
- **Recurring:** same merchant, ≥3 distinct months, ≥70% of gaps 25-35 days. *Fixed* if amount variation <10%.
- **Anomaly:** modified z-score >3.5 **and** ≥5× the typical amount; merchants with 6+ transactions are compared with their own history; falls back to mean absolute deviation when many amounts are identical.
- **Forecast:** weights 0.5/0.3/0.2 on the last three complete months per category, plus a least-squares trend as a sanity check.

## Known limitations
Identical same-day/same-amount purchases merge; PDF statements are not parsed; multi-currency is not supported; the ML fallback is trained on rule labels; Streamlit state is single-user (no login).
