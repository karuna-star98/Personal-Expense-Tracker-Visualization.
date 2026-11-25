# 9. Proof-building strategy (portfolio, LinkedIn, resume)

## What recruiters look for
1. A repo that runs in 3 commands. 2. Visible output (charts, screenshots). 3. Clean structure and tests. 4. A story: problem → approach → result.

## Evidence checklist
- [ ] README with hero image, quick start, architecture, sample output
- [ ] `images/` with dashboard screenshots and a 20-30 s GIF
- [ ] `reports/` with a real Excel + HTML report committed
- [ ] Green CI badge · 15+ tests
- [ ] A short Loom/YouTube demo linked in the README
- [ ] A blog/LinkedIn post explaining one interesting decision (e.g. *why median/MAD for anomalies*)

## Resume bullets (pick 3)
- Built an end-to-end expense analytics platform in Python (pandas, SQLite, Streamlit) that ingests heterogeneous bank/UPI CSVs, cleans data and auto-categorizes >99% of transactions with explainable rules.
- Designed an idempotent ETL pipeline with a UNIQUE-key schema; re-imports insert 0 duplicates.
- Implemented recurring-payment detection, robust anomaly detection (median/MAD) and a 3-month weighted forecast surfacing ₹2.4 lakh/yr of fixed commitments.
- Delivered an 8-tab interactive dashboard plus automated Excel/HTML reports; 15 pytest tests and GitHub Actions CI.

## LinkedIn post template
> I built a personal expense tracker that turns messy bank statements into answers. 🧾➡️📊
> Python · pandas · SQLite · Streamlit. It auto-detects columns in messy bank CSVs, auto-categorizes UPI transactions, flags unusual spends and forecasts next month.
> Biggest lesson: ISO dates like 2026-10-05 were silently read as 10 May when I told pandas dates were day-first - I added a test so it can never happen again.
> Code + demo: <link> #Python #DataAnalytics #Streamlit #SQL

## 4-week proof plan
Week 1 repo + README · Week 2 screenshots + GIF + demo video · Week 3 LinkedIn post + 2 comments on related posts · Week 4 add one new feature (e.g. PDF import) and post the change log.
