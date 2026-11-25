# 7. How to run the project

## One command (recommended)
```bash
python main.py run-all
```
Optional flags: `--month 2026-09`, `--keep-db`, `--regenerate`.

### Expected terminal output (from a real run)
```text
==================================================================
  STEP 1/6  LOAD DATA  (synthetic demo dataset -> SQLite)
==================================================================
   sample_expenses.csv : 591 rows read, 591 inserted
   bank statement      : 21 rows read -> dropped 2 invalid, 1 duplicate, 18 inserted
   categorized         : 584 transactions, 1 left Uncategorized
   ML fallback         : CV accuracy 98.5%, labelled 1 extra
   budgets             : 143 monthly category limits created

==================================================================
  STEP 2/6  CLEAN DATA CHECK
==================================================================
   transactions : 609   range: 01 Nov 2025 -> 19 Nov 2026
   months       : 13   accounts: Cash Wallet, HDFC Savings, ICICI Credit Card, SBI Savings
   report month : Oct 2026

==================================================================
  STEP 3/6  ANALYZE
==================================================================

==================================================================
  EXPENSE ANALYSIS - Oct 2026
==================================================================
  Total spend          :      ₹51,805
  Income               :      ₹67,000
  Savings              :      ₹15,195   (22.7% savings rate)
  Avg daily spend      :       ₹1,671   over 31 days
  Highest category     : Shopping (₹16,796, 32%)
  Health score         : 83/100 (Excellent)

  CATEGORY-WISE SPENDING
   Shopping                ₹16,796   32.4%  ############
   Rent & Housing          ₹15,200   29.3%  ###########
   Food & Dining            ₹6,143   11.9%  ####
   Transport                ₹5,219   10.1%  ####
   Bills & Utilities        ₹2,755    5.3%  ##
   Groceries                ₹1,878    3.6%  #
   Health & Fitness         ₹1,750    3.4%  #
   Entertainment            ₹1,664    3.2%  #
   Personal Transfers         ₹400    0.8%  #

  PAYMENT METHODS
   UPI                     ₹25,798   49.8%
   Credit Card             ₹17,325   33.4%
   Net Banking              ₹6,497   12.5%
   Debit Card               ₹1,138    2.2%
   Cash                     ₹1,047    2.0%

  MONTHLY TREND (last 6 complete months)
   May 2026   spend    ₹32,417   income    ₹68,000     -9%
   Jun 2026   spend    ₹47,336   income    ₹56,000    +46%
   Jul 2026   spend    ₹32,601   income    ₹55,000    -31%
   Aug 2026   spend    ₹45,172   income    ₹67,700    +39%
   Sep 2026   spend    ₹43,515   income    ₹55,000     -4%
   Oct 2026   spend    ₹51,805   income    ₹67,000    +19%

  BUDGET ALERTS
   ! OVER: Shopping is ₹11,796 over its ₹5,000 budget (336% used).
   ! OVER: Transport is ₹1,219 over its ₹4,000 budget (130% used).
   ! WARNING: Rent & Housing has used 100% of its budget (₹0 left).
   ! WARNING: Food & Dining has used 95% of its budget (₹357 left).
   ! WARNING: Entertainment has used 92% of its budget (₹136 left).
   ! WARNING: Bills & Utilities has used 92% of its budget (₹245 left).

  KEY INSIGHTS
   * You spent ₹51,805 in Oct 2026; the biggest category was Shopping at ₹16,796 (32% of spend).
   * You saved ₹15,195 - a savings rate of 23%, above the 20% rule of thumb.
   * Average daily spend was ₹1,671 across 31 days.
   * Spending rose 19% versus Sep 2026.
   * Biggest increase vs last month: Shopping (+₹9,557).
   * Wed is your most expensive day of the week (average ₹2,934).
   * Largest one-off expense: ₹7,999 on 'Amazon.in - Festive Sale Smart Watch' (28 Oct 2026).
   * Over budget in 2 categories; worst is Shopping by ₹11,796.
   * Close to the limit: Rent & Housing, Food & Dining, Entertainment, Bills & Utilities.
   * 8 recurring payments detected costing about ₹2,42,764 per year (largest: Rent Flat Landlord).
   * Unusual expense: ₹7,999 on 'Amazon.in - Festive Sale Smart Watch' is 5.8x your typical Shopping transaction.

  FORECAST Nov 2026: about ₹47,991 (trend check ₹43,786)

==================================================================
  STEP 4-6/6  CHARTS, REPORTS, EXPORTS
==================================================================

==================================================================
  FILES CREATED
==================================================================
   chart   outputs/charts/01_category_bar.png
   chart   outputs/charts/02_monthly_trend.png
   chart   outputs/charts/03_payment_method_donut.png
   chart   outputs/charts/04_daily_spending_trend.png
   chart   outputs/charts/05_category_donut.png
   chart   outputs/charts/06_weekday_category_heatmap.png
   chart   outputs/charts/07_budget_vs_actual.png
   chart   outputs/charts/08_cumulative_spend.png
   chart   outputs/charts/00_dashboard_summary.png
   csv     outputs/category_summary_2026-10.csv
   csv     outputs/monthly_summary.csv
   csv     outputs/payment_summary_2026-10.csv
   csv     outputs/budget_status_2026-10.csv
   csv     outputs/recurring_payments.csv
   csv     outputs/anomalies.csv
   report  reports/expense_report_2026-10.xlsx
   report  reports/expense_report_2026-10.html
   report  reports/expense_report_2026-10.txt
   images  images/  (copied for README)

  Done. Next: python main.py dashboard
```

## Command cheat-sheet
| Task | Command |
|---|---|
| Interactive dashboard | `python main.py dashboard` (or `streamlit run src/app_streamlit.py`) |
| Import your own CSV | `python main.py ingest statement.csv --account "HDFC Savings"` |
| CSV lists expenses as positive numbers | add `--expenses-positive` |
| Dates are mm/dd/yyyy | add `--monthfirst` |
| Add one transaction | `python main.py add --amount 450 --description "Zomato dinner" --method upi` |
| Add income | `python main.py add --amount 2000 --type income --description "Freelance payout"` |
| Set a budget | `python main.py budget set --month 2026-11 --category Shopping --limit 4000` |
| Check budgets | `python main.py budget check --month 2026-10` |
| Suggest budgets from history | `python main.py budget suggest --month 2026-11` |
| Re-run rules after editing them | `python main.py categorize --all` |
| Terminal analysis | `python main.py analyze --month 2026-10` |
| Charts / full report | `python main.py charts` / `python main.py report --month 2026-10` |
| Tests | `python -m pytest -q` |

## Using the dashboard
All filters are on the main page (no need to open the sidebar):
1. **Filter bar** - Period (a month, *All time* or *Custom range*), Accounts, Categories.
2. **Overview** - KPIs, health gauge, insights, category and payment donuts (hover for values).
3. **Categories** - category bar + table, **drill-down** (pick a category → monthly history, top merchants, all transactions), stacked mix (click legend items to hide/isolate).
4. **Trends** - choose which lines to show, daily chart with a **range slider to zoom**, cumulative vs budget pace, weekday heatmap, **compare two months**, forecast.
5. **Budgets** - progress, alerts, edit limits, apply data-driven suggestions.
6. **Insights** - **what-if simulator** (sliders cut a category by 0-50% and show monthly/yearly savings), recurring payments, unusual expenses.
7. **Transactions** - search, expense/income toggle, amount slider, sorting, fix a category, download CSV.
8. **Add / Import** - manual entry form, CSV upload with cleaning report, CSV template.
9. **Reports** - generate and download Excel / HTML / text.

The dashboard uses a fixed light theme (`.streamlit/config.toml`) so text is readable even if your browser is in dark mode. Run it from the project root (`python main.py dashboard` does this for you).
