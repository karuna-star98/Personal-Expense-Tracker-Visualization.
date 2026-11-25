"""Streamlit dashboard.  Run from the project root:   streamlit run src/app_streamlit.py"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:               # lets `streamlit run src/app_streamlit.py` find the `src` package
    sys.path.insert(0, str(ROOT))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import analyze, budget, categorize, config, ingest, models, pipeline, report
from src.config import CATEGORY_COLORS, PAYMENT_COLORS, inr

st.set_page_config(page_title="Personal Expense Tracker", page_icon="💸", layout="wide",
                   initial_sidebar_state="collapsed")

ACCENT, GOOD, BAD, WARN, MUTED, INK = "#4F46E5", "#10B981", "#EF4444", "#F59E0B", "#64748B", "#0F172A"

# Explicit colours everywhere, so the cards stay readable in light AND dark browser themes.
st.markdown("""
<style>
.block-container{padding-top:1.6rem;max-width:1350px}
div[data-testid="stMetric"]{background:#F8FAFC;border:1px solid #E2E8F0;border-left:4px solid #4F46E5;
  padding:14px 16px;border-radius:10px}
div[data-testid="stMetricLabel"] p{font-size:.78rem;text-transform:uppercase;letter-spacing:.05em;
  color:#64748B !important;font-weight:700}
div[data-testid="stMetricValue"], div[data-testid="stMetricValue"] div{color:#0F172A !important}
.insight{background:#FFFFFF;color:#0F172A;border:1px solid #E2E8F0;border-left:4px solid #4F46E5;
  border-radius:10px;padding:10px 14px;margin-bottom:8px}
.alert-over{background:#FEF2F2;color:#7F1D1D;border-left:4px solid #EF4444;padding:8px 12px;border-radius:6px;margin-bottom:6px}
.alert-warn{background:#FFFBEB;color:#78350F;border-left:4px solid #F59E0B;padding:8px 12px;border-radius:6px;margin-bottom:6px}
.filterbar{background:#F1F5F9;border-radius:12px;padding:6px 14px 2px 14px;margin-bottom:10px}
</style>""", unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# UI helpers (tolerant of Streamlit API changes: use_container_width -> width="stretch")
# ----------------------------------------------------------------------------
def show_chart(fig, key=None):
    try:
        st.plotly_chart(fig, width="stretch", theme=None, key=key)
    except TypeError:
        st.plotly_chart(fig, use_container_width=True, theme=None, key=key)


def show_table(df, **kwargs):
    try:
        st.dataframe(df, width="stretch", hide_index=True, **kwargs)
    except TypeError:
        st.dataframe(df, use_container_width=True, hide_index=True, **kwargs)


def style(fig, height=360, title=None, hover_x=False):
    fig.update_layout(template="plotly_white", height=height, margin=dict(l=10, r=10, t=50 if title else 20, b=10),
                      title=dict(text=title, font=dict(size=15, color=INK)) if title else None,
                      legend=dict(orientation="h", y=-0.2), paper_bgcolor="white", plot_bgcolor="white",
                      font=dict(family="Inter, Segoe UI, sans-serif", color=INK),
                      hovermode="x unified" if hover_x else "closest")
    return fig


def money_cols(cols):
    return {c: st.column_config.NumberColumn(c.replace("_", " ").title(), format="₹%.0f") for c in cols}


# ----------------------------------------------------------------------------
# Data + sidebar (data tools only; all filters live on the main page)
# ----------------------------------------------------------------------------
models.init_db()
df_all = analyze.fetch_frame()

with st.sidebar:
    st.header("Data tools")
    if df_all.empty:
        st.info("The database is empty. Load the demo data, or import your own CSV in the **Add / Import** tab.")
    if st.button("Load demo data" if df_all.empty else "Reset to demo data"):
        with st.spinner("Building demo database..."):
            pipeline.load_demo(reset=True, regenerate=False)
        st.rerun()

st.title("💸 Personal Expense Tracker")
st.caption("Import → clean → categorize → store (SQLite) → analyze → visualize → export  |  amounts in INR  |  "
           "hover, zoom and click everything")

if df_all.empty:
    st.warning("No data yet. Open the sidebar (top-left **»**) and click **Load demo data**.")
    st.stop()

complete = analyze.complete_months(df_all)
months_desc = sorted(df_all["month"].unique(), reverse=True)
dm = analyze.default_month(df_all)
last_date, first_date = df_all["tx_date"].max(), df_all["tx_date"].min()


def month_option_label(m):
    if m in ("All time", "Custom range"):
        return m
    return analyze.month_label(m) + ("  (month-to-date)" if m not in complete else "")


# ============================================================================
# FILTER BAR (main page)
# ============================================================================
st.markdown("<div class='filterbar'>", unsafe_allow_html=True)
f1, f2, f3 = st.columns([1.3, 2, 2])
period_options = months_desc + ["All time", "Custom range"]
with f1:
    period = st.selectbox("📅 Period", period_options, index=period_options.index(dm), format_func=month_option_label)
accounts = sorted(df_all["account"].unique())
with f2:
    acc_sel = st.multiselect("🏦 Accounts", accounts, default=accounts)
with f3:
    cat_sel = st.multiselect("🏷️ Categories (empty = all)", sorted(df_all["category"].unique()), default=[])
start = end = None
if period == "Custom range":
    picked = st.date_input("Date range", value=(first_date.date(), last_date.date()),
                           min_value=first_date.date(), max_value=last_date.date())
    if isinstance(picked, (list, tuple)) and len(picked) == 2:
        start, end = pd.Timestamp(picked[0]), pd.Timestamp(picked[1])
    else:
        start, end = first_date, last_date
st.markdown("</div>", unsafe_allow_html=True)

# df      = accounts only (history for trends, forecast, budgets, recurring ...)
# dview   = accounts + category filter + custom range (what the selected period shows)
df = df_all[df_all["account"].isin(acc_sel)] if acc_sel else df_all.iloc[0:0]
dview = df[df["category"].isin(cat_sel)] if cat_sel else df
if period == "Custom range":
    dview = dview[(dview["tx_date"] >= start) & (dview["tx_date"] <= end)]
    month, days = None, max(int((end - start).days) + 1, 1)
    period_name = f"{start:%d %b %Y} → {end:%d %b %Y}"
else:
    month = None if period == "All time" else period
    days = analyze.period_days(df_all, month)
    period_name = month_option_label(period)
dfm = analyze.filter_month(dview, month)
k = analyze.kpis(dfm, days)

bud_month = month or dm
budgets_df = budget.get_budgets(bud_month)
status = budget.status_from_frame(analyze.filter_month(df, bud_month), budgets_df)
health = analyze.financial_health_score(df, bud_month, status if len(status) else None)

tabs = st.tabs(["📊 Overview", "🗂️ Categories", "📈 Trends", "🎯 Budgets", "🔎 Insights",
                "🧾 Transactions", "➕ Add / Import", "📄 Reports"])

# ============================================================================
# 1. OVERVIEW
# ============================================================================
with tabs[0]:
    prev = str(pd.Period(month, "M") - 1) if month else None
    kp = analyze.kpis(analyze.filter_month(df, prev), 30) if prev and prev in set(df["month"]) else None
    c = st.columns(5)
    c[0].metric("Total spend", inr(k["total_spend"]),
                None if not kp else f"{(k['total_spend'] - kp['total_spend']):+,.0f} vs prev. month", delta_color="inverse")
    c[1].metric("Income", inr(k["income"]))
    c[2].metric("Savings", inr(k["savings"]), f"{k['savings_rate']:.0f}% savings rate")
    c[3].metric("Avg daily spend", inr(k["avg_daily_spend"]))
    c[4].metric("Top category", k["top_category"], f"{k['top_category_share']:.0f}% of spend", delta_color="off")

    if month and month not in complete:
        st.info(f"{analyze.month_label(month)} is still in progress - figures cover data up to {last_date:%d %b %Y}.")

    left, right = st.columns([1, 2])
    with left:
        g = go.Figure(go.Indicator(
            mode="gauge+number", value=health["score"], title={"text": f"Financial health - {health['label']}"},
            gauge={"axis": {"range": [0, 100]}, "bar": {"color": ACCENT},
                   "steps": [{"range": [0, 45], "color": "#FEE2E2"}, {"range": [45, 65], "color": "#FEF3C7"},
                             {"range": [65, 100], "color": "#D1FAE5"}]}))
        show_chart(style(g, 280), key="gauge")
        with st.expander("How is the score calculated?"):
            st.write(pd.Series(health["components"], name="points").to_frame())
            st.caption("Savings rate (40) + budget discipline (30) + spend stability (15) + needs-vs-wants split (15).")
    with right:
        st.subheader("Key insights")
        for text in analyze.generate_insights(df, bud_month, status if len(status) else None):
            st.markdown(f"<div class='insight'>{text}</div>", unsafe_allow_html=True)

    a, b = st.columns(2)
    cs = analyze.category_summary(dview, month)
    with a:
        if len(cs):
            fig = px.pie(cs, names="category", values="spend", hole=0.55, color="category", color_discrete_map=CATEGORY_COLORS)
            fig.update_traces(textposition="inside", textinfo="percent", pull=[0.03] * len(cs))
            show_chart(style(fig, 380, f"Category split - {period_name}"), key="ov_donut")
    with b:
        ps = analyze.payment_summary(dview, month)
        if len(ps):
            fig = px.pie(ps, names="payment_method", values="spend", hole=0.55, color="payment_method",
                         color_discrete_map=PAYMENT_COLORS)
            fig.update_traces(textposition="inside", textinfo="percent", pull=[0.03] * len(ps))
            show_chart(style(fig, 380, "Payment methods"), key="ov_pay")

# ============================================================================
# 2. CATEGORIES (+ drill-down)
# ============================================================================
with tabs[1]:
    cs = analyze.category_summary(dview, month)
    if cs.empty:
        st.warning("No expenses for this selection.")
    else:
        a, b = st.columns([3, 2])
        with a:
            d = cs.sort_values("spend")
            fig = px.bar(d, x="spend", y="category", orientation="h", color="category", color_discrete_map=CATEGORY_COLORS,
                         text=d["spend"].map(inr))
            fig.update_traces(textposition="outside", cliponaxis=False)
            fig.update_layout(showlegend=False, xaxis_title=None, yaxis_title=None)
            show_chart(style(fig, 420, f"Category-wise spending - {period_name}"), key="cat_bar")
        with b:
            show_table(cs.rename(columns={"share_pct": "share_%"}), column_config={
                **money_cols(["spend", "avg_tx", "max_tx"]),
                "share_%": st.column_config.ProgressColumn("Share %", format="%.0f%%", min_value=0, max_value=100)})

        st.subheader("🔍 Drill down into a category")
        pick = st.selectbox("Pick a category to explore", cs["category"].tolist(), key="drill")
        dd = analyze.expenses(dfm[dfm["category"] == pick])
        hist = analyze.expenses(df[df["category"] == pick])
        c = st.columns(4)
        c[0].metric(f"{pick} spend", inr(dd["spend"].sum()))
        c[1].metric("Transactions", f"{len(dd):,}")
        c[2].metric("Average", inr(dd["spend"].mean() if len(dd) else 0))
        c[3].metric("Largest", inr(dd["spend"].max() if len(dd) else 0))
        x1, x2 = st.columns(2)
        with x1:
            m_hist = hist.groupby("month")["spend"].sum().reset_index()
            m_hist = m_hist[m_hist["month"].isin(complete)]
            if len(m_hist):
                fig = px.bar(m_hist, x="month", y="spend", color_discrete_sequence=[CATEGORY_COLORS.get(pick, ACCENT)])
                fig.update_layout(xaxis_title=None, yaxis_title=None)
                show_chart(style(fig, 300, f"{pick} - month by month", hover_x=True), key="drill_month")
        with x2:
            mer = analyze.top_merchants(dfm[dfm["category"] == pick], None, 8)
            if len(mer):
                fig = px.bar(mer.sort_values("spend"), x="spend", y="merchant", orientation="h",
                             color_discrete_sequence=[CATEGORY_COLORS.get(pick, ACCENT)])
                fig.update_layout(xaxis_title=None, yaxis_title=None)
                show_chart(style(fig, 300, "Top merchants"), key="drill_mer")
        with st.expander(f"All {pick} transactions in this period"):
            show_table(dd.sort_values("tx_date", ascending=False)[["tx_date", "description", "spend", "payment_method", "account"]],
                       column_config={"spend": st.column_config.NumberColumn("Amount", format="₹%.0f"),
                                      "tx_date": st.column_config.DateColumn("Date", format="DD MMM YYYY")})

        st.subheader("Category mix over time")
        exp = analyze.expenses(df)
        exp = exp[exp["month"].isin(complete)]
        mix = exp.groupby(["month", "category"])["spend"].sum().reset_index()
        fig = px.bar(mix, x="month", y="spend", color="category", color_discrete_map=CATEGORY_COLORS)
        fig.update_layout(xaxis_title=None, yaxis_title=None, barmode="stack")
        show_chart(style(fig, 400, hover_x=False), key="cat_mix")
        st.caption("Tip: click a legend item to hide a category, double-click to isolate it.")

# ============================================================================
# 3. TRENDS
# ============================================================================
with tabs[2]:
    ms = analyze.monthly_summary(df)
    ms_c = ms[ms["month"].isin(complete)]
    if len(ms_c):
        opts = st.multiselect("Show on the monthly chart", ["Spending", "Income", "Savings"],
                              default=["Spending", "Income", "Savings"])
        labels = ms_c["month"].map(analyze.month_label)
        fig = go.Figure()
        if "Spending" in opts:
            fig.add_bar(x=labels, y=ms_c["spend"], name="Spending", marker_color=ACCENT, opacity=0.85)
        if "Income" in opts:
            fig.add_scatter(x=labels, y=ms_c["income"], name="Income", mode="lines+markers", line=dict(color=GOOD, dash="dash"))
        if "Savings" in opts:
            fig.add_scatter(x=labels, y=ms_c["savings"], name="Savings", mode="lines+markers", line=dict(color=WARN))
        show_chart(style(fig, 380, "Monthly income, spending and savings (complete months)", hover_x=True), key="tr_month")

    dsp = analyze.daily_spend(dview, month)
    show_avg = st.checkbox("Show 7-day moving average", value=True)
    if len(dsp):
        fig = go.Figure()
        fig.add_bar(x=dsp["date"], y=dsp["spend"], name="Daily spend", marker_color="#C7D2FE")
        if show_avg:
            fig.add_scatter(x=dsp["date"], y=dsp["ma7"], name="7-day average", line=dict(color=ACCENT, width=3))
        fig.update_xaxes(rangeslider_visible=True)
        show_chart(style(fig, 430, f"Daily spending - {period_name}  (drag the slider underneath to zoom)", hover_x=True), key="tr_daily")

    a, b = st.columns(2)
    with a:
        if len(dsp) and month:
            fig = go.Figure()
            fig.add_scatter(x=dsp["date"], y=dsp["cumulative"], name="Actual", fill="tozeroy", line=dict(color=ACCENT))
            total_b = float(status["limit"].sum()) if len(status) else 0
            if total_b:
                s0, e0 = analyze.month_bounds(month)
                n = (e0 - s0).days + 1
                fig.add_scatter(x=pd.date_range(s0, e0), y=[total_b * (i + 1) / n for i in range(n)],
                                name="Budget pace", line=dict(color=BAD, dash="dash"))
            show_chart(style(fig, 360, "Cumulative spend vs budget pace", hover_x=True), key="tr_cum")
        else:
            st.info("Pick a single month to see cumulative spend vs budget pace.")
    with b:
        pv = analyze.weekday_category_matrix(dview, month)
        if len(pv):
            fig = go.Figure(go.Heatmap(z=pv.values, x=list(pv.columns), y=list(pv.index), colorscale="Purples",
                                       hovertemplate="%{y} on %{x}: ₹%{z:,.0f}<extra></extra>"))
            show_chart(style(fig, 360, "When do you spend? (category × weekday)"), key="tr_heat")

    st.subheader("⚖️ Compare two months")
    if len(complete) >= 2:
        cc = st.columns(2)
        ma = cc[0].selectbox("Month A", complete, index=len(complete) - 2, format_func=analyze.month_label, key="cmp_a")
        mb = cc[1].selectbox("Month B", complete, index=len(complete) - 1, format_func=analyze.month_label, key="cmp_b")
        ca = analyze.category_summary(df, ma).assign(month=analyze.month_label(ma))
        cb = analyze.category_summary(df, mb).assign(month=analyze.month_label(mb))
        both = pd.concat([ca, cb])
        if len(both):
            fig = px.bar(both, x="category", y="spend", color="month", barmode="group",
                         color_discrete_sequence=["#A5B4FC", ACCENT])
            fig.update_layout(xaxis_title=None, yaxis_title=None)
            show_chart(style(fig, 380, hover_x=True), key="cmp_chart")
            tot_a, tot_b = ca["spend"].sum(), cb["spend"].sum()
            st.metric(f"{analyze.month_label(mb)} vs {analyze.month_label(ma)}", inr(tot_b),
                      f"{tot_b - tot_a:+,.0f}", delta_color="inverse")

    fc = analyze.forecast_next_month(df)
    if fc["next_month"]:
        st.subheader(f"🔮 Forecast - {analyze.month_label(fc['next_month'])}")
        c = st.columns(3)
        c[0].metric("Expected spend", inr(fc["total"]), help="Weighted average of the last 3 complete months, by category")
        c[1].metric("Linear-trend check", inr(fc["trend_total"]))
        c[2].metric("Trend per month", f"{fc['trend_slope']:+,.0f}")
        show_table(fc["by_category"], column_config=money_cols(["forecast"]))

# ============================================================================
# 4. BUDGETS
# ============================================================================
with tabs[3]:
    st.subheader(f"Budget status - {analyze.month_label(bud_month)}")
    if month is None:
        st.caption("No single month selected - showing the latest complete month.")
    if len(status):
        for msg in budget.budget_alerts(status)[:6]:
            st.markdown(f"<div class='{'alert-over' if msg.startswith('OVER') else 'alert-warn'}'>{msg}</div>",
                        unsafe_allow_html=True)
        d = status.sort_values("utilization_pct")
        fig = go.Figure()
        fig.add_bar(y=d["category"], x=d["limit"], orientation="h", name="Budget", marker_color="#E2E8F0")
        fig.add_bar(y=d["category"], x=d["spend"], orientation="h", name="Spent", width=0.4,
                    marker_color=[BAD if s == "Over budget" else WARN if s == "Warning" else GOOD for s in d["status"]])
        fig.update_layout(barmode="overlay")
        show_chart(style(fig, 420, "Budget vs actual"), key="bud_chart")
        show_table(status, column_config={**money_cols(["limit", "spend", "remaining", "over_by"]),
                   "utilization_pct": st.column_config.ProgressColumn("Used %", format="%.0f%%", min_value=0, max_value=150)})
    else:
        st.info("No budgets for this month yet. Add one below or use the data-driven suggestion.")

    st.subheader("Set or update a budget")
    c = st.columns([2, 2, 1])
    cat_choice = c[0].selectbox("Category", config.EXPENSE_CATEGORIES, key="bud_cat")
    cur = budgets_df.set_index("category")["limit"].to_dict().get(cat_choice, 0.0)
    new_limit = c[1].number_input("Monthly limit (₹)", min_value=0.0, value=float(cur), step=500.0)
    if c[2].button("Save budget"):
        budget.set_budget(bud_month, cat_choice, new_limit)
        st.success(f"Saved {inr(new_limit)} for {cat_choice}")
        st.rerun()
    sug = budget.suggest_budgets(df_all, bud_month)
    with st.expander("Suggest budgets from my last 3 months (+10% buffer)"):
        if len(sug):
            show_table(sug, column_config=money_cols(["avg_spend", "suggested_limit"]))
            if st.button("Apply suggested budgets to this month"):
                for r in sug.itertuples():
                    budget.set_budget(bud_month, r.category, r.suggested_limit)
                st.rerun()
        else:
            st.write("Not enough history yet.")

# ============================================================================
# 5. INSIGHTS (+ what-if simulator)
# ============================================================================
with tabs[4]:
    st.subheader("🎛️ What-if savings simulator")
    st.caption(f"Drag the sliders to cut spending in a category and see what you would save "
               f"(based on {analyze.month_label(bud_month)}).")
    base = analyze.category_summary(df, bud_month)
    base = base[base["category"] != "Rent & Housing"].head(6)
    inc_m = analyze.kpis(analyze.filter_month(df, bud_month), 30)
    if len(base):
        sc = st.columns(3)
        saving = 0.0
        for i, r in enumerate(base.itertuples()):
            cut = sc[i % 3].slider(f"Cut {r.category} by %  ({inr(r.spend)})", 0, 50, 0, 5, key=f"cut_{r.category}")
            saving += r.spend * cut / 100
        base_total = analyze.kpis(analyze.filter_month(df, bud_month), 30)["total_spend"]
        new_rate = (inc_m["income"] - (base_total - saving)) / inc_m["income"] * 100 if inc_m["income"] else 0
        m = st.columns(4)
        m[0].metric("Saved per month", inr(saving))
        m[1].metric("Saved per year", inr(saving * 12))
        m[2].metric("New spend", inr(base_total - saving))
        m[3].metric("New savings rate", f"{new_rate:.0f}%", f"{new_rate - inc_m['savings_rate']:+.1f} pts")

    rec = analyze.detect_recurring(df)
    st.subheader("Recurring payments (subscriptions & bills)")
    if len(rec):
        c = st.columns(3)
        c[0].metric("Detected", len(rec))
        c[1].metric("Monthly cost", inr(rec["avg_amount"].sum()))
        c[2].metric("Yearly cost", inr(rec["annual_cost"].sum()))
        fig = px.bar(rec.sort_values("annual_cost"), x="annual_cost", y="merchant", orientation="h",
                     color="category", color_discrete_map=CATEGORY_COLORS)
        fig.update_layout(xaxis_title="Yearly cost (₹)", yaxis_title=None)
        show_chart(style(fig, 340), key="rec_chart")
        show_table(rec, column_config=money_cols(["avg_amount", "annual_cost"]))
    else:
        st.write("No recurring payments detected yet (needs 3+ months of history).")
    st.subheader("Unusual expenses")
    an = analyze.detect_anomalies(df)
    if len(an):
        st.caption("Flagged with a robust z-score (median/MAD): far above what is normal for that merchant or category.")
        show_table(an, column_config=money_cols(["spend", "typical"]))
    else:
        st.write("Nothing unusual found.")

# ============================================================================
# 6. TRANSACTIONS
# ============================================================================
with tabs[5]:
    f = st.columns([2, 2, 1.2])
    q = f[0].text_input("🔍 Search description", placeholder="e.g. swiggy, rent, amazon")
    sort_by = f[1].selectbox("Sort by", ["Newest first", "Oldest first", "Largest expense", "Largest income"])
    only = f[2].radio("Show", ["All", "Expenses", "Income"], horizontal=True)
    view = dfm
    if only == "Expenses":
        view = view[view["amount"] < 0]
    elif only == "Income":
        view = view[view["amount"] > 0]
    if q:
        view = view[view["description"].str.contains(q, case=False, na=False, regex=False)]
    if len(view) > 1 and float(view["amount"].min()) < float(view["amount"].max()):
        lo, hi = st.slider("Amount range (₹, expenses are negative)", float(view["amount"].min()), float(view["amount"].max()),
                           (float(view["amount"].min()), float(view["amount"].max())))
        view = view[(view["amount"] >= lo) & (view["amount"] <= hi)]
    order = {"Newest first": ("tx_date", False), "Oldest first": ("tx_date", True),
             "Largest expense": ("amount", True), "Largest income": ("amount", False)}[sort_by]
    view = view.sort_values(order[0], ascending=order[1])
    st.caption(f"{len(view):,} transactions  |  net {inr(view['amount'].sum())}")
    show_cols = ["id", "tx_date", "description", "category", "amount", "payment_method", "account", "category_source"]
    show_table(view[show_cols], column_config={
        "tx_date": st.column_config.DateColumn("Date", format="DD MMM YYYY"),
        "amount": st.column_config.NumberColumn("Amount", format="₹%.2f")})
    st.download_button("⬇️ Download filtered transactions (CSV)", view[show_cols].to_csv(index=False).encode(),
                       "transactions.csv", "text/csv")

    with st.expander("✏️ Fix a category manually"):
        recent = view.head(100)
        if len(recent):
            lookup = recent.set_index("id")
            pick_tx = st.selectbox("Transaction", recent["id"].tolist(),
                                   format_func=lambda i: f"{lookup.loc[i, 'tx_date']:%d %b} - {lookup.loc[i, 'description'][:45]} "
                                                         f"({lookup.loc[i, 'category']})")
            new_cat = st.selectbox("New category", list(config.CATEGORY_META), key="fix_cat")
            if st.button("Update category"):
                categorize.set_category(int(pick_tx), new_cat)
                st.success("Updated - manual labels are never overwritten by the rules.")
                st.rerun()

# ============================================================================
# 7. ADD / IMPORT
# ============================================================================
with tabs[6]:
    a, b = st.columns(2)
    with a:
        st.subheader("Add a transaction")
        with st.form("manual_entry", clear_on_submit=True):
            kind = st.radio("Type", ["Expense", "Income"], horizontal=True)
            when = st.date_input("Date", value=pd.Timestamp.today().date())
            amt = st.number_input("Amount (₹)", min_value=0.0, step=10.0)
            desc = st.text_input("Description", placeholder="e.g. Swiggy dinner")
            cat = st.selectbox("Category", ["Auto-detect"] + list(config.CATEGORY_META))
            method = st.selectbox("Payment method", config.PAYMENT_METHODS)
            account = st.text_input("Account", value="Manual")
            submitted = st.form_submit_button("Add transaction")
        if submitted:
            try:
                ok = ingest.add_manual_transaction(when, desc, amt, kind.lower(), None if cat == "Auto-detect" else cat,
                                                   method, account)
                categorize.run()
                (st.success("Transaction added.") if ok else st.warning("Duplicate - an identical transaction already exists."))
                if ok:
                    st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    with b:
        st.subheader("Import a CSV")
        st.caption("Columns are auto-detected (Date / Narration / Withdrawal / Deposit / Amount ...). "
                   "Re-importing is safe: duplicates are skipped.")
        up = st.file_uploader("CSV file", type=["csv"])
        acc_name = st.text_input("Account name for this file", value="Imported")
        dayfirst = st.checkbox("Dates are day-first (dd/mm/yyyy)", value=True)
        exp_pos = st.checkbox("Expenses are positive numbers in this file", value=False)
        if up is not None and st.button("Import file"):
            try:
                rep = ingest.import_csv(up, account=acc_name, dayfirst=dayfirst, expenses_positive=exp_pos)
                cat_res = categorize.run()
                st.success(f"Imported {rep['inserted']} new rows ({rep['skipped']} duplicates skipped).")
                st.json({k_: v for k_, v in rep.items()})
                st.caption(f"Categorized {cat_res['processed']} rows; {cat_res['uncategorized']} remain uncategorized. "
                           "Reload the page to see them in the charts.")
            except Exception as exc:                              # friendly message instead of a stack trace
                st.error(f"Could not import: {exc}")
        template = "Date,Description,Amount,Payment Method,Account,Category\n2026-11-01,Swiggy Order #1234,-349,UPI,HDFC Savings,\n"
        st.download_button("Download CSV template", template.encode(), "expense_template.csv", "text/csv")

# ============================================================================
# 8. REPORTS
# ============================================================================
with tabs[7]:
    st.subheader("Export a monthly report")
    rep_month = st.selectbox("Month", months_desc, index=months_desc.index(dm), format_func=month_option_label, key="rep_month")
    if st.button("Generate Excel + HTML + text report"):
        with st.spinner("Building charts and reports..."):
            res = report.generate_all(rep_month, df=df_all, copy_images=False)
        st.session_state["report_paths"] = {k_: str(v) for k_, v in res.items() if k_ in ("excel", "html", "text")}
        st.session_state["report_month"] = rep_month
    paths = st.session_state.get("report_paths")
    if paths:
        st.success(f"Reports for {analyze.month_label(st.session_state['report_month'])} saved in the reports/ folder.")
        c = st.columns(3)
        for col, (label, key, mime) in zip(c, [
                ("Excel workbook", "excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                ("HTML report (print to PDF)", "html", "text/html"), ("Text summary", "text", "text/plain")]):
            p = Path(paths[key])
            col.download_button(label, p.read_bytes(), p.name, mime)
