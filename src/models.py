"""SQLite schema and connection helpers."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from . import config

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS categories(
    id     INTEGER PRIMARY KEY,
    name   TEXT UNIQUE NOT NULL,
    parent TEXT,
    kind   TEXT DEFAULT 'expense'
);

CREATE TABLE IF NOT EXISTS transactions(
    id              INTEGER PRIMARY KEY,
    tx_date         TEXT NOT NULL,                 -- ISO date YYYY-MM-DD
    description     TEXT NOT NULL,
    amount          REAL NOT NULL CHECK(amount <> 0),  -- negative = expense, positive = income
    currency        TEXT DEFAULT 'INR',
    account         TEXT NOT NULL DEFAULT 'Manual',    -- e.g. 'HDFC Savings', 'Cash Wallet'
    payment_method  TEXT DEFAULT 'Other',              -- UPI / Credit Card / Cash ...
    category_id     INTEGER,
    category_source TEXT,                              -- csv | rule | ml | manual
    raw_source      TEXT,
    tags            TEXT,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tx_date, description, amount, account),
    FOREIGN KEY(category_id) REFERENCES categories(id)
);

CREATE TABLE IF NOT EXISTS budgets(
    id           INTEGER PRIMARY KEY,
    month        TEXT NOT NULL,                    -- '2026-10'
    category_name TEXT NOT NULL,
    limit_amount REAL NOT NULL CHECK(limit_amount >= 0),
    UNIQUE(month, category_name)
);

CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions(tx_date);
CREATE INDEX IF NOT EXISTS idx_tx_category ON transactions(category_id);
"""


def resolve(path: str | Path | None = None) -> Path:
    return Path(path) if path else config.DB_PATH


@contextmanager
def connect(path: str | Path | None = None):
    """Open a connection with foreign keys on; commit on success, always close."""
    con = sqlite3.connect(resolve(path))
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db(path: str | Path | None = None) -> Path:
    """Create tables (idempotent) and seed the base categories."""
    db = resolve(path)
    db.parent.mkdir(parents=True, exist_ok=True)
    with connect(db) as con:
        con.executescript(SCHEMA)
        for name, meta in config.CATEGORY_META.items():
            con.execute(
                "INSERT OR IGNORE INTO categories(name, kind) VALUES (?, ?)",
                (name, meta["kind"]),
            )
    return db


def reset_db(path: str | Path | None = None) -> Path:
    """Delete the database file and recreate it empty."""
    db = resolve(path)
    if db.exists():
        db.unlink()
    return init_db(db)


def category_map(con: sqlite3.Connection, create_missing: list[str] | None = None) -> dict[str, int]:
    """Return {category name: id}; optionally create unknown names first."""
    for name in create_missing or []:
        if name:
            con.execute("INSERT OR IGNORE INTO categories(name, kind) VALUES (?, 'expense')", (name,))
    return {row[0]: row[1] for row in con.execute("SELECT name, id FROM categories")}
