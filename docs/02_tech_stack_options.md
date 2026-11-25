# 2. Tech stack options

| Layer | Beginner | Intermediate (**used here**) | Advanced / production |
|---|---|---|---|
| Language | Python 3.10+ | Python 3.10+ | Python 3.12 + type checking (mypy) |
| Data | csv module | **pandas, numpy** | polars, DuckDB |
| Storage | CSV files | **SQLite (`sqlite3`)** | PostgreSQL + SQLAlchemy + Alembic |
| Charts | Matplotlib | **Matplotlib + Seaborn (static), Plotly (interactive)** | Superset / Metabase / Power BI |
| UI | Terminal menu | **Streamlit** | FastAPI + React |
| Reports | Text file | **Excel (xlsxwriter), HTML (Jinja2)** | PDF via WeasyPrint, scheduled e-mail |
| ML | none | **scikit-learn (TF-IDF + Naive Bayes)** | embeddings / LLM classification |
| Quality | manual runs | **pytest + GitHub Actions** | pre-commit, ruff, coverage gates, Docker |

## Why these choices?
- **SQLite** is a real SQL database that needs no installation - ideal for a portfolio project and easy to swap for PostgreSQL later (all SQL is isolated in `models.py`, `ingest.py`, `budget.py`).
- **pandas** is the industry standard for tabular analysis and what interviewers expect.
- **Matplotlib for files, Plotly for the dashboard**: static PNGs are perfect for GitHub proof; Plotly gives hover/zoom for users.
- **Streamlit** builds a professional dashboard in one Python file.
- Pydantic (mentioned in the brief) was left out to keep dependencies small - validation is done in `ingest.standardize`. It would be a natural upgrade for an API version.
