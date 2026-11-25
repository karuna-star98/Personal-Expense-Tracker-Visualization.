# 11. Interview preparation

## 60-second pitch
"I built a personal expense tracker in Python. It imports bank or UPI CSVs - even messy ones with different headers and split debit/credit columns - cleans them with pandas, auto-categorizes merchants with ordered rules, and stores everything in SQLite with a unique key so re-imports are idempotent. On top of that I compute KPIs, budgets with alerts, recurring-payment detection, anomaly detection with a robust z-score, and a next-month forecast. Results are shown in a Streamlit dashboard and exported as Excel and HTML reports. It has 15 tests and CI."

## Demo script (3 minutes)
1. `python main.py run-all` - show the cleaning report (invalid rows, duplicate).
2. Run `ingest` on the same file again → "0 inserted" (idempotent).
3. Dashboard: change month, show the health gauge, alerts, anomalies.
4. Add an expense in the form → category auto-detected.
5. Generate the Excel report.

## Technical questions and model answers
**1. Why SQLite and not just CSV/pandas?** A database gives constraints (UNIQUE, CHECK), indexes, SQL aggregation and a clear upgrade path to PostgreSQL. The UNIQUE key is what makes imports idempotent.

**2. How do you avoid duplicate transactions?** Rows are de-duplicated inside the file, then `INSERT OR IGNORE` against `UNIQUE(tx_date, description, amount, account)`. Limitation: two identical same-day purchases merge; a bank reference number would fix that.

**3. How does column auto-detection work?** A dictionary of lower-case header aliases per field (`narration`, `particulars` → description; `withdrawal amt.` → debit). If there is no single amount column, amount = credit − debit.

**4. Tell me about a bug you found.** pandas `format="mixed"` with `dayfirst=True` read `2026-10-05` as 10 May. I now detect ISO strings and parse them year-first, and a unit test locks it in.

**5. Why rules instead of ML for categories?** Explainable, deterministic, no training data needed, >99% coverage on the demo set. ML (TF-IDF + Naive Bayes) is an optional fallback; I explain that its ~98% CV accuracy is optimistic because labels come from the rules.

**6. Why does rule order matter?** First match wins. "Swiggy Instamart" must be Groceries before "swiggy" makes it Food; "Amazon Prime" must be Entertainment before "amazon" makes it Shopping.

**7. How does anomaly detection work?** Modified z-score `0.6745·(x − median)/MAD` > 3.5 *and* ≥ 5× typical. Median/MAD are robust - a huge purchase can't inflate the baseline the way it inflates mean/std. Merchants with 6+ transactions are judged against their own history; if MAD is 0 (many identical fees) I use mean absolute deviation.

**8. How do you detect subscriptions?** Group by cleaned merchant name; need 3+ distinct months and ≥70% of gaps between 25 and 35 days. Amount variation under 10% → "Fixed", otherwise "Variable".

**9. How is the forecast built and how accurate is it?** Weighted average (50/30/20) of the last three complete months per category, cross-checked with a linear trend. It is a baseline, not a prediction of one-off purchases; I'd evaluate it by back-testing MAPE on rolling months.

**10. What is a "complete" month and why does it matter?** A month whose last calendar day is covered by data. Treating the latest partial month as complete would show a fake spending drop.

**11. How is the health score computed?** Savings rate 40, budget discipline 30, stability 15, needs-vs-wants 15 = 100. It is a transparent heuristic, shown in the UI.

**12. How do you handle negative amounts / refunds?** Sign convention: expense < 0, income > 0. A refund is a positive amount categorized as Income; a production system would net it against the original category.

**13. How would you scale this?** Move to PostgreSQL + SQLAlchemy, add per-user tables and auth, run ingestion as background jobs, cache aggregates, containerize with Docker.

**14. How do you test it?** Unit tests for parsers, rules and maths; a database test with a temp file; an end-to-end test that generates data, imports, analyzes, draws charts and writes reports in a temp directory and checks money is conserved (category totals = total spend).

**15. What would you improve?** PDF statement parsing, bank reference IDs for dedupe, merchant normalization via a lookup table, per-user auth, goal tracking, scheduled e-mail alerts.

**16. pandas vs SQL for aggregation?** SQL for budget status over the full table (set-based, indexed); pandas where I need rolling windows, pivots and statistics.

**17. How do you protect privacy?** Local SQLite, no network calls, DB git-ignored, synthetic demo data. For a hosted version: encryption at rest, auth, no raw narrations in logs.

**18. Why Streamlit?** Fastest path from analysis code to an interactive UI; analytics logic stays in pure functions, so the UI is a thin layer and could be replaced by FastAPI + React.

**19. How do you format Indian currency?** Custom `inr()` helper that groups digits as 12,34,567 (lakh/crore system).

**20. What did you learn?** Cleaning is most of the work; idempotency and tests make a data pipeline trustworthy; explain results in words, not just charts.

## SQL warm-ups on this schema
```sql
-- spend per category in Oct 2026
SELECT c.name, ROUND(-SUM(t.amount),0) AS spend
FROM transactions t JOIN categories c ON c.id=t.category_id
WHERE t.amount<0 AND strftime('%Y-%m',t.tx_date)='2026-10'
GROUP BY c.name ORDER BY spend DESC;

-- months where spending exceeded 90% of income
WITH m AS (SELECT strftime('%Y-%m',tx_date) mth,
                  SUM(CASE WHEN amount<0 THEN -amount END) spend,
                  SUM(CASE WHEN amount>0 THEN amount END) income
           FROM transactions GROUP BY 1)
SELECT mth, spend, income FROM m WHERE spend > 0.9*income;
```
