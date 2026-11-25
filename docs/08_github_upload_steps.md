# 8. GitHub upload steps

## 1. One-time setup
```bash
git config --global user.name  "Your Name"
git config --global user.email "you@example.com"
```

## 2. Create the repository
On github.com → **New repository** → name `Personal-Expense-Tracker-Visualization` → Public → *do not* add README/license (they already exist) → **Create**.

## 3. Push the project
```bash
cd Personal-Expense-Tracker-Visualization
python main.py run-all          # make sure outputs/, images/, reports/ are fresh
git init
git add .
git commit -m "feat: personal expense tracker with analytics and dashboard"
git branch -M main
git remote add origin https://github.com/<your-username>/Personal-Expense-Tracker-Visualization.git
git push -u origin main
```
Check that `db/expenses.db` is **not** in the commit (it is git-ignored) and that `images/` and `outputs/` **are**.

## 4. Polish the repo page
- **About** (gear icon): description + topics `python pandas sqlite streamlit data-visualization personal-finance data-analysis`
- Replace `<Your Name>` in `LICENSE` and `<your-username>` in the README.
- Pin the repository on your profile.
- Add dashboard screenshots to `images/` and reference them in the README.
- Confirm the green ✔ from GitHub Actions (CI tab).

## 5. Good commit history (looks professional)
Make several small commits instead of one big one, e.g. `feat: csv ingestion`, `feat: categorization rules`, `feat: budgets`, `feat: dashboard`, `test: add pipeline test`, `docs: add README`.

## 6. Optional: free deployment
Push to GitHub → share.streamlit.io → *New app* → pick the repo, branch `main`, file `src/app_streamlit.py`. First visit: click **Load demo data**.
