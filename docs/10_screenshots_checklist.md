# 10. Screenshots checklist

Run `python main.py dashboard`, set the browser to ~1400 px wide, and capture:

| # | Screen | Save as |
|---|---|---|
| 1 | Overview tab - KPIs, health gauge, insights | `images/dash_01_overview.png` |
| 2 | Categories tab - bar + stacked mix | `images/dash_02_categories.png` |
| 3 | Trends tab - monthly, daily, heatmap | `images/dash_03_trends.png` |
| 4 | Budgets tab with red/amber alerts | `images/dash_04_budgets.png` |
| 5 | Insights tab - recurring + anomalies | `images/dash_05_insights.png` |
| 6 | Add / Import tab after importing the messy bank CSV (cleaning report visible) | `images/dash_06_import.png` |
| 7 | Terminal after `python main.py run-all` | `images/terminal_run_all.png` |
| 8 | Excel report - Summary sheet with charts | `images/excel_summary.png` |
| 9 | `pytest` green output | `images/pytest_passing.png` |

Tips: use a clean browser profile, hide bookmarks, crop to the content, keep file size under 500 KB (tinypng.com), and record a 20-30 s GIF (ScreenToGif / Kap) of switching tabs and changing the month.

Already generated for you by `run-all`: all nine static charts in `images/` (`00_dashboard_summary.png` … `08_cumulative_spend.png`).
