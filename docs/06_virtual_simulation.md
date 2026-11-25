# 6. Virtual simulation - a day in the life of the tracker

*Persona: Aarav, 26, software engineer in Pune. Salary ₹55,000, rent ₹14,000. Uses UPI for most things. All numbers below come from the shipped synthetic dataset.*

**Day 1 - export.** Aarav downloads his HDFC statement (`hdfc_statement_nov2026.csv`). It is messy: headers are `Narration`, `Withdrawal Amt.`, `Deposit Amt.`; dates look like `05/11/26`; numbers contain commas; the last two lines are a pending ATM entry and an "END OF STATEMENT" footer; one row is duplicated.

**Day 1 - import.** `python main.py ingest hdfc_statement_nov2026.csv --account "HDFC Savings"`
The tool detects the columns itself and reports: *21 rows read → 2 invalid dropped, 1 duplicate removed, 18 inserted*. Running the same command again inserts **0** rows - the import is idempotent.

**Day 1 - categorize.** `UPI-SWIGGY-ORDER-#13887-1033608178@YBL` becomes *Food & Dining*; `Swiggy Instamart` becomes *Groceries* (rule order matters); `Amazon Prime Annual Membership` becomes *Entertainment* while `Amazon.in Order` becomes *Shopping*. Only `Shree Traders` is unknown - Aarav labels it *Shopping* once and that label is never overwritten.

**Week 2 - the dashboard.** Overview for October shows spend ₹51,805 vs income ₹67,000 (22.7% savings rate), health score 83/100. Insight: *Shopping jumped +₹9,557 vs September* - the festive-sale smart watch (₹7,999). Alerts: Shopping 336% of budget, Transport 130%.

**Week 3 - hidden costs.** The Insights tab lists 8 recurring payments (rent, gym, electricity, broadband, Netflix, Jio, Spotify...) costing about ₹2.4 lakh a year, and 3 unusual expenses (headphones ₹18,999, hospital bill ₹14,500, smart watch ₹7,999).

**Month end - reporting.** `python main.py report --month 2026-10` writes an Excel workbook (9 sheets, native charts), a printable HTML report and a text summary. The forecast for November: about ₹47,991.

**What Aarav changes.** He raises Transport to ₹4,500, sets Shopping to ₹4,000 and cancels nothing - but now he *knows* where the money goes.
