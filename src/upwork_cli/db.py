"""SQLite database for local job tracking, proposals, and bookmarks."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Generator, Optional

from upwork_cli.config import DB_FILE, ensure_config_dir

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    skills TEXT,
    budget_amount REAL,
    budget_currency TEXT,
    duration TEXT,
    engagement TEXT,
    client_country TEXT,
    client_total_spent REAL,
    client_total_hires INTEGER,
    client_feedback REAL,
    created_at TEXT,
    fetched_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scores (
    job_id TEXT PRIMARY KEY REFERENCES jobs(id),
    score INTEGER NOT NULL,
    reasoning TEXT,
    scored_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT REFERENCES jobs(id),
    job_title TEXT,
    content TEXT NOT NULL,
    tone TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS bookmarks (
    job_id TEXT PRIMARY KEY REFERENCES jobs(id),
    note TEXT,
    bookmarked_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS watch_seen (
    job_id TEXT PRIMARY KEY,
    search_term TEXT,
    seen_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def get_db_path() -> str:
    ensure_config_dir()
    return str(DB_FILE)


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA)


def upsert_job(job: dict[str, Any]) -> None:
    with get_connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO jobs
            (id, title, description, skills, budget_amount, budget_currency,
             duration, engagement, client_country, client_total_spent,
             client_total_hires, client_feedback, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                job.get("id", ""),
                job.get("title", ""),
                job.get("description", ""),
                json.dumps(job.get("skills", [])),
                job.get("budget_amount"),
                job.get("budget_currency"),
                job.get("duration"),
                job.get("engagement"),
                job.get("client_country"),
                job.get("client_total_spent"),
                job.get("client_total_hires"),
                job.get("client_feedback"),
                job.get("created_at"),
            ),
        )


def save_score(job_id: str, score: int, reasoning: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO scores (job_id, score, reasoning) VALUES (?, ?, ?)",
            (job_id, score, reasoning),
        )


def save_proposal(job_id: str, job_title: str, content: str, tone: str = "professional") -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO proposals (job_id, job_title, content, tone) VALUES (?, ?, ?, ?)",
            (job_id, job_title, content, tone),
        )
        return cursor.lastrowid or 0


def save_bookmark(job_id: str, note: str = "") -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO bookmarks (job_id, note) VALUES (?, ?)",
            (job_id, note),
        )


def remove_bookmark(job_id: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM bookmarks WHERE job_id = ?", (job_id,))


def get_bookmarks() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT b.job_id, b.note, b.bookmarked_at, j.title, j.budget_amount, j.budget_currency
            FROM bookmarks b LEFT JOIN jobs j ON b.job_id = j.id
            ORDER BY b.bookmarked_at DESC"""
        ).fetchall()
        return [dict(r) for r in rows]


def get_proposals(limit: int = 20) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM proposals ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def mark_seen(job_id: str, search_term: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO watch_seen (job_id, search_term) VALUES (?, ?)",
            (job_id, search_term),
        )


def is_seen(job_id: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM watch_seen WHERE job_id = ?", (job_id,)
        ).fetchone()
        return row is not None


def get_jobs_with_scores(limit: int = 50) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT j.*, s.score, s.reasoning
            FROM jobs j LEFT JOIN scores s ON j.id = s.job_id
            ORDER BY s.score DESC NULLS LAST, j.fetched_at DESC
            LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
