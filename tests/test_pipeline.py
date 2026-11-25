import tempfile
from pathlib import Path

from src import analyze, budget, generate_data, models, plots, report


def test_end_to_end_pipeline_in_temp_dir():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        db = d / "e2e.db"
        files = generate_data.write_sample_files(d / "data")
        from src import ingest, categorize
        models.init_db(db)
        a = ingest.import_csv(files["sample"], db_path=db)
        b = ingest.import_csv(files["bank"], db_path=db, account="HDFC Savings")
        assert a["inserted"] > 400 and b["duplicates_removed"] == 1 and b["dropped_invalid"] == 2
        categorize.run(db)
        df = analyze.fetch_frame(db)
        assert df["category"].eq("Uncategorized").mean() < 0.03            # rules cover >97% of the synthetic data
        month = analyze.default_month(df)
        budget.apply_default_budgets(sorted(df["month"].unique()), db)
        S = report.build_summary(month, db, df)
        charts = plots.generate_all_charts(df, month, S["budget"], S["health"], out_dir=d / "charts")
        assert len(charts) == 9 and all(p.stat().st_size > 5000 for p in charts.values())
        x = report.export_excel(S, d / "r.xlsx"); h = report.export_html(S, d / "r.html", charts); t = report.export_text(S, d / "r.txt")
        assert x.stat().st_size > 5000 and "Personal Expense Report" in h.read_text(encoding="utf-8")
        assert "KEY INSIGHTS" in t.read_text(encoding="utf-8")
        # money conservation: category totals equal total spend
        assert abs(S["category"]["spend"].sum() - S["kpis"]["total_spend"]) < 0.01
