"""
SQLite database setup for user accounts and query history.
Uses Python's built-in sqlite3 — no ORM dependency required.
"""

import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "wiki_qa.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                username   TEXT    UNIQUE NOT NULL,
                password_hash TEXT  NOT NULL,
                created_at REAL    NOT NULL DEFAULT (unixepoch())
            );

            CREATE TABLE IF NOT EXISTS history (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id       INTEGER NOT NULL REFERENCES users(id),
                query         TEXT    NOT NULL,
                answer        TEXT    NOT NULL,
                primary_title TEXT    NOT NULL,
                primary_url   TEXT    NOT NULL,
                latency_ms    REAL,
                cached        INTEGER DEFAULT 0,
                created_at    REAL    NOT NULL DEFAULT (unixepoch())
            );

            CREATE INDEX IF NOT EXISTS idx_history_user
                ON history(user_id, created_at DESC);
        """)


# ---------------------------------------------------------------------------
# User operations
# ---------------------------------------------------------------------------

def create_user(username: str, password_hash: str) -> Optional[int]:
    try:
        with get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, password_hash),
            )
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None   # Username already taken


def get_user_by_username(username: str) -> Optional[Dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[Dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else None


# ---------------------------------------------------------------------------
# History operations
# ---------------------------------------------------------------------------

def save_history(
    user_id: int,
    query: str,
    answer: str,
    primary_title: str,
    primary_url: str,
    latency_ms: float,
    cached: bool,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO history
               (user_id, query, answer, primary_title, primary_url, latency_ms, cached)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, query, answer, primary_title, primary_url, latency_ms, int(cached)),
        )


def get_history(user_id: int, limit: int = 20) -> List[Dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT id, query, answer, primary_title, primary_url, latency_ms, cached, created_at
               FROM history WHERE user_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
