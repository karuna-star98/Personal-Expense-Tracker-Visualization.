# 3. Architecture and folder structure

## Data flow
```
CSV ──► ingest.standardize ──► ingest.upsert ──► SQLite ──► categorize.run ──► SQLite
                                                   │
                                                   ▼
                                            analyze.fetch_frame (DataFrame)
                         ┌───────────────┬─────────┼──────────────┬───────────────┐
                         ▼               ▼         ▼              ▼               ▼
                    plots.py (PNG)   app_streamlit  report.py   budget.py     main.py (CLI)
```

## Layers and responsibilities
| Module | Responsibility | Pure? |
|---|---|---|
| `config.py` | paths, category list, colours, `inr()` formatter | yes |
| `models.py` | schema, connection context manager, `reset_db` | I/O |
| `generate_data.py` | synthetic transactions + messy bank export | yes (seeded) |
| `ingest.py` | detect columns, parse, clean, insert | mostly (DB only in `upsert`) |
| `categorize.py` | rules, ML fallback, manual override | DB |
| `analyze.py` | KPIs, summaries, recurring, anomalies, forecast, score, insights | **pure** (DataFrame in → out) |
| `budget.py` | set/check budgets; `compute_status` is pure | DB + pure |
| `plots.py` | figures (each takes an optional Axes) | pure |
| `report.py` | Excel/HTML/TXT/CSV | files |
| `pipeline.py` | demo workflow used by both CLI and app | orchestration |

Keeping `analyze.py` pure (no database calls) makes it easy to unit-test and reuse in the notebook, CLI and dashboard.

## Database (ER view)
```
categories 1 ──── * transactions        budgets (month, category_name) -> limit
  id, name          category_id          UNIQUE(month, category_name)
                    UNIQUE(tx_date, description, amount, account)
```
Sign convention: expense `< 0`, income `> 0`.

## Folder structure
```
data/        input CSVs (synthetic samples)      db/       SQLite file (git-ignored)
src/         application code                    tests/    pytest suite
notebooks/   exploratory analysis                outputs/  CSV summaries + charts
images/      README images                       reports/  monthly Excel/HTML/TXT
docs/        guides                              .github/  CI workflow
```
