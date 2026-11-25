"""End-to-end pipelines shared by the CLI (main.py) and the Streamlit app."""
from __future__ import annotations

from . import analyze, budget, categorize, config, generate_data, ingest, models


def load_demo(db_path=None, reset: bool = True, regenerate: bool = False, use_ml: bool = True) -> dict:
    """Generate (if needed) and load the synthetic dataset: ingest -> categorize -> default budgets."""
    config.ensure_dirs()
    if regenerate or not (config.SAMPLE_CSV.exists() and config.BANK_CSV.exists()):
        generate_data.write_sample_files()
    db = models.reset_db(db_path) if reset else models.init_db(db_path)

    r_sample = ingest.import_csv(config.SAMPLE_CSV, db_path=db)                       # standard template
    r_bank = ingest.import_csv(config.BANK_CSV, db_path=db, account="HDFC Savings")   # messy bank export
    cat = categorize.run(db, use_ml=use_ml)
    df = analyze.fetch_frame(db)
    n_budgets = budget.apply_default_budgets(sorted(df["month"].unique()), db) if not df.empty else 0
    return {"sample_import": r_sample, "bank_import": r_bank, "categorize": cat,
            "transactions": len(df), "budgets_created": n_budgets, "default_month": analyze.default_month(df)}
