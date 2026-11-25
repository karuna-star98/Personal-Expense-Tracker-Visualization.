# 1. Project explanation (in simple words)

## What problem does it solve?
Everyone spends money through UPI, cards, cash and net banking, but the data is scattered across bank apps and PDFs. This project gathers it in one place and answers practical questions:

- Where did my money go this month?
- Am I within budget? Which category is going out of control?
- Which subscriptions am I paying for without noticing?
- Was that purchase unusual? What will next month cost?

## How it works (the 7 steps)
1. **Import** - read a CSV from any bank. The program finds the right columns by itself.
2. **Clean** - remove empty/invalid rows and duplicates, fix dates, amounts (`₹1,299.50`, `(500)`, `250 Dr`) and payment-method names.
3. **Categorize** - match descriptions such as *Swiggy*, *Uber*, *Netflix* to categories using ordered keyword rules. Unknown merchants can be guessed by a small ML model.
4. **Store** - save everything in a SQLite database (a single file, no server needed).
5. **Analyze** - compute totals, trends, budgets, recurring payments, anomalies, a forecast and a health score.
6. **Visualize** - static PNG charts and an interactive dashboard.
7. **Export** - Excel, HTML (print to PDF), text and CSV reports.

## Real-world use
Personal budgeting, freelancers tracking expenses, small shop owners, students learning data analysis, and as the core of fintech apps (Walnut, Money Manager, CRED insights).

## Skills demonstrated
Python · pandas · SQL/SQLite · data cleaning · visualization · statistics (robust z-score) · basic ML · software engineering (modules, CLI, tests, CI) · dashboarding · reporting.

## What is "extra" compared to the original brief?
The brief asked for CSV import, a category pie chart and a monthly line chart. This version adds: bank-statement auto-detection, an idempotent SQLite pipeline, budgets with alerts, recurring-payment detection, anomaly detection, forecast, financial health score, plain-English insights, a Plotly dashboard, Excel/HTML reports, tests and CI.
