"""Auto-categorisation: keyword rules first, optional Naive-Bayes fallback for the rest."""
from __future__ import annotations

import re

import pandas as pd

from . import config, models

# Order matters: the FIRST matching category wins.
# (e.g. "Swiggy Instamart" must hit Groceries before "swiggy" hits Food, and
#  "Amazon Prime" must hit Entertainment before "amazon" hits Shopping.)
# Patterns run against a normalised description: lower-case, punctuation -> space.
RULES: dict[str, list[str]] = {
    "Rent & Housing": [r"\brent\b", r"\blandlord\b", r"\bmaintenance\b", r"\bsociety\b", r"\bhousing\b"],
    "Bills & Utilities": [r"electric", r"\bmsedcl\b", r"\bmseb\b", r"\bbescom\b", r"water bill", r"wi ?fi", r"broadband",
                          r"fibernet", r"\bairtel\b", r"\bjio\b", r"\bvodafone\b", r"\bbsnl\b", r"recharge", r"\bdth\b",
                          r"tata play", r"\blpg\b", r"gas bill", r"insurance"],
    "Groceries": [r"big ?basket", r"blinkit", r"zepto", r"instamart", r"\bd ?mart\b", r"reliance fresh", r"big bazaar",
                  r"grocer", r"supermart", r"kirana", r"provision", r"general store", r"nature s basket"],
    "Entertainment": [r"netflix", r"amazon prime", r"prime video", r"spotify", r"youtube premium", r"hotstar",
                      r"bookmyshow", r"book my show", r"\bpvr\b", r"\binox\b", r"cinema", r"gaming", r"steam"],
    "Transport": [r"\buber\b", r"\bola\b", r"rapido", r"\bmetro\b", r"petrol", r"diesel", r"\bfuel\b", r"indian oil",
                  r"\bhp petrol", r"bpcl", r"hpcl", r"fastag", r"\bbus\b", r"parking", r"\btoll\b", r"\bauto\b",
                  r"\bcab\b", r"\bcabs\b", r"namma yatri"],
    "Travel": [r"irctc", r"makemytrip", r"goibibo", r"redbus", r"indigo", r"air india", r"vistara", r"akasa",
               r"spicejet", r"\boyo\b", r"airbnb", r"booking com", r"cleartrip", r"ixigo", r"resort"],
    "Health & Fitness": [r"pharmacy", r"apollo", r"medplus", r"\b1mg\b", r"pharmeasy", r"netmeds", r"hospital",
                         r"clinic", r"doctor", r"\bdr\b", r"diagnostic", r"pathology", r"dental", r"\bgym\b",
                         r"cult ?fit", r"fitness", r"yoga", r"medical"],
    "Education": [r"udemy", r"coursera", r"unacademy", r"byju", r"upgrad", r"skillshare", r"tuition", r"college fee",
                  r"school fee", r"exam fee", r"\bcourse\b", r"library"],
    "Food & Dining": [r"swiggy", r"zomato", r"restaurant", r"\bcafe\b", r"coffee", r"starbucks", r"domino", r"pizza",
                      r"burger", r"mcdonald", r"\bkfc\b", r"subway", r"\bchai\b", r"biryani", r"dhaba", r"bakery",
                      r"barbeque", r"haldiram", r"canteen", r"\bmess\b", r"dining", r"\bccd\b", r"tapri"],
    "Shopping": [r"amazon", r"flipkart", r"myntra", r"ajio", r"meesho", r"nykaa", r"decathlon", r"croma",
                 r"reliance digital", r"lenskart", r"ikea", r"pantaloons", r"zara", r"westside", r"stationer",
                 r"\bmall\b", r"electronics", r"fashion"],
    "Personal Transfers": [r"\bp2p\b", r"transfer to", r"sent to"],
}
INCOME_PATTERNS = [r"salary", r"payout", r"refund", r"reimburse", r"cashback", r"interest credit", r"dividend",
                   r"stipend", r"freelance", r"bonus"]

_COMPILED = {cat: [re.compile(p) for p in pats] for cat, pats in RULES.items()}
_INCOME = [re.compile(p) for p in INCOME_PATTERNS]


def normalize_text(desc: str) -> str:
    """'UPI-SWIGGY-ORDER-#13887-1033@YBL' -> 'upi swiggy order 13887 1033 ybl'."""
    text = re.sub(r"[^a-z0-9&]+", " ", str(desc).lower())
    return re.sub(r"\s+", " ", text).strip()


def classify(description: str, amount: float | None = None) -> str:
    """Return a category name for one transaction description."""
    text = normalize_text(description)
    if amount is not None and amount > 0:
        return "Income"            # money in is income (salary, refunds, cashback ...)
    for category, patterns in _COMPILED.items():
        if any(p.search(text) for p in patterns):
            return category
    if any(p.search(text) for p in _INCOME):
        return "Income"
    return "Uncategorized"


def run(db_path=None, recategorize: bool = False, use_ml: bool = False, ml_threshold: float = 0.6) -> dict:
    """Assign categories to transactions that have none (or re-run rules for rule/ml-labelled rows).

    Manual and CSV-provided labels are never overwritten.
    """
    models.init_db(db_path)
    with models.connect(db_path) as con:
        ids = models.category_map(con, create_missing=list(config.CATEGORY_META))
        where = ("category_id IS NULL OR category_source IN ('rule','ml')" if recategorize
                 else "category_id IS NULL")
        df = pd.read_sql_query(f"SELECT id, description, amount FROM transactions WHERE {where}", con)
        updates = [(ids[classify(r.description, r.amount)], "rule", int(r.id)) for r in df.itertuples()]
        con.executemany("UPDATE transactions SET category_id=?, category_source=? WHERE id=?", updates)
        n_unc = con.execute(
            "SELECT COUNT(*) FROM transactions t JOIN categories c ON c.id=t.category_id WHERE c.name='Uncategorized'"
        ).fetchone()[0]
    result = {"processed": len(df), "uncategorized": int(n_unc)}
    if use_ml:
        result["ml"] = apply_ml(db_path, threshold=ml_threshold)
        with models.connect(db_path) as con:
            result["uncategorized"] = con.execute(
                "SELECT COUNT(*) FROM transactions t JOIN categories c ON c.id=t.category_id "
                "WHERE c.name='Uncategorized'").fetchone()[0]
    return result


# ----------------------------------------------------------------------------
# Optional ML fallback (needs scikit-learn)
# ----------------------------------------------------------------------------
def _ml_training_frame(con) -> pd.DataFrame:
    return pd.read_sql_query(
        """SELECT t.id, t.description, c.name AS category, t.category_source
           FROM transactions t JOIN categories c ON c.id = t.category_id
           WHERE t.amount < 0 AND c.name NOT IN ('Uncategorized','Income')""", con)


def _ml_clean(desc: str) -> str:
    return re.sub(r"\d+", " ", normalize_text(desc))


def apply_ml(db_path=None, threshold: float = 0.6) -> dict:
    """Train Multinomial Naive Bayes on already-labelled history and label 'Uncategorized' rows."""
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.model_selection import cross_val_score
        from sklearn.naive_bayes import MultinomialNB
        from sklearn.pipeline import make_pipeline
    except ImportError:                                           # pragma: no cover
        return {"skipped": "scikit-learn is not installed"}

    with models.connect(db_path) as con:
        train = _ml_training_frame(con)
        if len(train) < 30 or train["category"].nunique() < 2:
            return {"skipped": "not enough labelled history (need 30+ rows)"}
        model = make_pipeline(TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4)), MultinomialNB(alpha=0.1))
        X, y = train["description"].map(_ml_clean), train["category"]
        counts = y.value_counts()
        keep = y.isin(counts[counts >= 5].index)           # rare classes break cross-validation
        cv = float(cross_val_score(model, X[keep], y[keep], cv=3).mean()) if keep.sum() >= 30 else float("nan")
        model.fit(X, y)

        unk = pd.read_sql_query(
            """SELECT t.id, t.description FROM transactions t JOIN categories c ON c.id=t.category_id
               WHERE c.name='Uncategorized' AND t.amount < 0""", con)
        applied = 0
        if not unk.empty:
            proba = model.predict_proba(unk["description"].map(_ml_clean))
            ids = models.category_map(con)
            for row, p in zip(unk.itertuples(), proba):
                if p.max() >= threshold:
                    con.execute("UPDATE transactions SET category_id=?, category_source='ml' WHERE id=?",
                                (ids[str(model.classes_[p.argmax()])], int(row.id)))
                    applied += 1
    return {"cv_accuracy": round(cv, 3), "applied": applied, "candidates": len(unk)}


def set_category(tx_id: int, category: str, db_path=None) -> None:
    """Manually override one transaction's category (never overwritten by rules later)."""
    with models.connect(db_path) as con:
        ids = models.category_map(con, create_missing=[category])
        con.execute("UPDATE transactions SET category_id=?, category_source='manual' WHERE id=?",
                    (ids[category], int(tx_id)))


if __name__ == "__main__":
    print(run())
