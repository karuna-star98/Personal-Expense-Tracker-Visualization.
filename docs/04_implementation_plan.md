# 4. Step-by-step implementation plan

| Phase | Goal | Deliverable | Where in the code |
|---|---|---|---|
| 1. Setup | virtual env, folders, git | project skeleton | `requirements.txt`, `.gitignore` |
| 2. Data | create realistic sample data | 12-month CSV + messy bank CSV | `generate_data.py` |
| 3. Schema | design the database | 3 tables + indexes | `models.py` |
| 4. Ingest | detect columns, clean, load | idempotent importer + cleaning report | `ingest.py` |
| 5. Categorize | rules, ordering, overrides | categories on every row | `categorize.py` |
| 6. Analyze | KPIs and summaries | DataFrames | `analyze.py` |
| 7. Budgets | limits, status, alerts | budget table + alerts | `budget.py` |
| 8. Visualize | charts + dashboard | PNGs, Streamlit app | `plots.py`, `app_streamlit.py` |
| 9. Report | Excel / HTML / TXT | `reports/` | `report.py` |
| 10. Harden | tests, CI, docs | green pipeline | `tests/`, `.github/` |

## Suggested timeline (part-time)
- Weekend 1: phases 1-4 (get data into SQLite)
- Weekend 2: phases 5-7 (insights)
- Weekend 3: phases 8-9 (visuals and reports)
- Weekend 4: phase 10 + README + screenshots + LinkedIn post

## Definition of done
`python main.py run-all` finishes without errors, `python -m pytest` is green, the README shows real charts, and a stranger can run the project with three commands.
