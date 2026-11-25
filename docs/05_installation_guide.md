# 5. Installation guide

## Requirements
- Python 3.10 or newer (`python --version`)
- Git (optional, for cloning)
- ~200 MB disk space

## Windows (PowerShell)
```powershell
git clone https://github.com/<your-username>/Personal-Expense-Tracker-Visualization.git
cd Personal-Expense-Tracker-Visualization
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
If activation is blocked: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.

## macOS / Linux
```bash
git clone https://github.com/<your-username>/Personal-Expense-Tracker-Visualization.git
cd Personal-Expense-Tracker-Visualization
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Verify
```bash
python -m pytest -q        # needs: pip install -r requirements-dev.txt
python main.py run-all
```

## Troubleshooting
| Problem | Fix |
|---|---|
| `ModuleNotFoundError: src` | run commands from the project root (the folder containing `main.py`) |
| `No module named streamlit` | `pip install -r requirements.txt` inside the activated venv |
| ₹ symbol shows as a box in a chart | install the *DejaVu Sans* font (bundled with Matplotlib - reinstall matplotlib) |
| Dashboard shows "database is empty" | click **Load demo data** in the sidebar or run `python main.py run-all` |
| Port 8501 busy | `streamlit run src/app_streamlit.py --server.port 8502` |
| Text looks faded / invisible in the dashboard | run from the project root so `.streamlit/config.toml` (light theme) is used: `python main.py dashboard` |
| Dashboard looks static | use the filter bar at the top of the page; hover charts, drag the slider under the daily chart, open the drill-down and what-if sections |
