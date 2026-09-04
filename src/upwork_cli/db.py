"""SQLite database for local job tracking, proposals, and bookmarks."""

import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from upwork_cli.config import DB_FILE, ensure_config_dir
from upwork_cli.models import Bookmark, JobPosting, Proposal

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    skills TEXT,
    budget_amount REAL,
    budget_currency TEXT,
    duration TEXT,
    duration_label TEXT DEFAULT '',
    engagement TEXT,
    client_country TEXT,
    client_total_spent REAL,
    client_total_hires INTEGER,
    client_feedback REAL,
    client_verified INTEGER DEFAULT 0,
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

CREATE TABLE IF NOT EXISTS pipeline (
    job_id TEXT PRIMARY KEY REFERENCES jobs(id),
    stage TEXT NOT NULL DEFAULT 'found',
    moved_at TEXT DEFAULT CURRENT_TIMESTAMP,
    notes TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS pipeline_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT REFERENCES jobs(id),
    from_stage TEXT,
    to_stage TEXT NOT NULL,
    moved_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

MIGRATIONS = [
    "ALTER TABLE proposals ADD COLUMN outcome TEXT DEFAULT NULL",
    "ALTER TABLE jobs ADD COLUMN category TEXT DEFAULT ''",
    "ALTER TABLE jobs ADD COLUMN subcategory TEXT DEFAULT ''",
    "ALTER TABLE jobs ADD COLUMN client_verified INTEGER DEFAULT 0",
    "ALTER TABLE jobs ADD COLUMN duration_label TEXT DEFAULT ''",
]


def _run_migrations(conn: sqlite3.Connection) -> None:
    """Apply lightweight schema migrations (idempotent)."""
    for sql in MIGRATIONS:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass  # Column already exists


def get_db_path() -> str:
    ensure_config_dir()
    return str(DB_FILE)


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
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
        _run_migrations(conn)


def upsert_job(job: JobPosting) -> None:
    """Insert or replace a cached job posting."""
    data = job.to_db_dict()
    columns = list(data)
    with get_connection() as conn:
        conn.execute(
            f"""INSERT OR REPLACE INTO jobs ({", ".join(columns)})
            VALUES ({", ".join("?" * len(columns))})""",
            tuple(
                json.dumps(data["skills"])
                if name == "skills"
                else int(bool(data["client_verified"]))
                if name == "client_verified"
                else data[name]
                for name in columns
            ),
        )


def save_score(job_id: str, score: int, reasoning: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO scores (job_id, score, reasoning) VALUES (?, ?, ?)",
            (job_id, score, reasoning),
        )


def save_proposal(
    job_id: str, job_title: str, content: str, tone: str = "professional"
) -> int:
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO jobs (id, title) VALUES (?, ?)",
            (job_id, job_title or job_id),
        )
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


def get_bookmarks() -> list[Bookmark]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT b.job_id, b.note, b.bookmarked_at, j.title, j.budget_amount, j.budget_currency
            FROM bookmarks b LEFT JOIN jobs j ON b.job_id = j.id
            ORDER BY b.bookmarked_at DESC"""
        ).fetchall()
        return [Bookmark.from_db_row(r) for r in rows]


def get_proposal(proposal_id: int) -> Proposal | None:
    """Look up a single stored Proposal, or None if there is no such id."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM proposals WHERE id = ?", (proposal_id,)
        ).fetchone()
        return Proposal.from_db_row(row) if row else None


def get_latest_proposal() -> Proposal | None:
    """The most recently created Proposal, or None if there are none."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM proposals ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        return Proposal.from_db_row(row) if row else None


def get_proposals(limit: int = 20) -> list[Proposal]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM proposals ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [Proposal.from_db_row(r) for r in rows]


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


def get_unscored_jobs(limit: int = 50) -> list[JobPosting]:
    """Cached jobs that have never been successfully scored, newest first.

    Filtered in SQL rather than in the caller: ranking unscored jobs last and
    then discarding the scored ones from the first N strands every unscored
    job beyond the window.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT j.*
            FROM jobs j LEFT JOIN scores s ON j.id = s.job_id
            WHERE s.score IS NULL
            ORDER BY j.fetched_at DESC
            LIMIT ?""",
            (limit,),
        ).fetchall()
        return [JobPosting.from_db_row(r) for r in rows]


def get_job(job_id: str) -> JobPosting | None:
    """Look up a single cached job posting, or None if it is not cached."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return JobPosting.from_db_row(row) if row else None


# ---------------------------------------------------------------------------
# Pipeline functions
# ---------------------------------------------------------------------------


def set_pipeline_stage(job_id: str, stage: str, notes: str = "") -> None:
    """Move a job to a pipeline stage (upsert). Records transition history."""
    with get_connection() as conn:
        # Get current stage (if any)
        row = conn.execute(
            "SELECT stage FROM pipeline WHERE job_id = ?", (job_id,)
        ).fetchone()
        from_stage = row["stage"] if row else None

        # Upsert pipeline row
        conn.execute(
            """INSERT INTO pipeline (job_id, stage, notes, moved_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(job_id) DO UPDATE SET
                stage = excluded.stage,
                notes = excluded.notes,
                moved_at = excluded.moved_at""",
            (job_id, stage, notes),
        )

        # Record history
        conn.execute(
            """INSERT INTO pipeline_history (job_id, from_stage, to_stage)
            VALUES (?, ?, ?)""",
            (job_id, from_stage, stage),
        )


def set_pipeline_stage_if_not_exists(job_id: str, stage: str) -> None:
    """Set pipeline stage only if the job is not already in the pipeline."""
    with get_connection() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO pipeline (job_id, stage)
            VALUES (?, ?)""",
            (job_id, stage),
        )


def get_pipeline_jobs(stage: str | None = None) -> list[dict[str, Any]]:
    """Get jobs in the pipeline, optionally filtered by stage."""
    with get_connection() as conn:
        if stage:
            rows = conn.execute(
                """SELECT p.*, j.title, j.budget_amount, j.budget_currency,
                          j.client_country, j.category, s.score
                FROM pipeline p
                LEFT JOIN jobs j ON p.job_id = j.id
                LEFT JOIN scores s ON p.job_id = s.job_id
                WHERE p.stage = ?
                ORDER BY p.moved_at DESC""",
                (stage,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT p.*, j.title, j.budget_amount, j.budget_currency,
                          j.client_country, j.category, s.score
                FROM pipeline p
                LEFT JOIN jobs j ON p.job_id = j.id
                LEFT JOIN scores s ON p.job_id = s.job_id
                ORDER BY p.moved_at DESC""",
            ).fetchall()
        return [dict(r) for r in rows]


def get_pipeline_stats() -> dict[str, Any]:
    """Get pipeline statistics: stage counts, win rate, top categories."""
    with get_connection() as conn:
        # Stage counts
        rows = conn.execute(
            "SELECT stage, COUNT(*) as cnt FROM pipeline GROUP BY stage"
        ).fetchall()
        stage_counts = {r["stage"]: r["cnt"] for r in rows}

        # Win rate
        won = stage_counts.get("won", 0)
        applied = (
            stage_counts.get("applied", 0)
            + stage_counts.get("interviewing", 0)
            + won
            + stage_counts.get("lost", 0)
        )
        win_rate = (won / applied * 100) if applied > 0 else 0.0

        # Top categories
        cat_rows = conn.execute(
            """SELECT j.category, COUNT(*) as cnt
            FROM pipeline p JOIN jobs j ON p.job_id = j.id
            WHERE j.category != ''
            GROUP BY j.category ORDER BY cnt DESC LIMIT 5"""
        ).fetchall()
        top_categories = [
            {"category": r["category"], "count": r["cnt"]} for r in cat_rows
        ]

        return {
            "stage_counts": stage_counts,
            "total": sum(stage_counts.values()),
            "win_rate": round(win_rate, 1),
            "top_categories": top_categories,
        }


def get_pipeline_history(job_id: str | None = None) -> list[dict[str, Any]]:
    """Get pipeline transition history, optionally for a specific job."""
    with get_connection() as conn:
        if job_id:
            rows = conn.execute(
                """SELECT h.*, j.title FROM pipeline_history h
                LEFT JOIN jobs j ON h.job_id = j.id
                WHERE h.job_id = ?
                ORDER BY h.moved_at DESC""",
                (job_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT h.*, j.title FROM pipeline_history h
                LEFT JOIN jobs j ON h.job_id = j.id
                ORDER BY h.moved_at DESC LIMIT 50""",
            ).fetchall()
        return [dict(r) for r in rows]


def mark_proposal_outcome(proposal_id: int, outcome: str) -> None:
    """Mark a proposal's outcome (won/lost/no_response)."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE proposals SET outcome = ? WHERE id = ?",
            (outcome, proposal_id),
        )


def get_winning_proposals() -> list[Proposal]:
    """Every Proposal whose recorded Outcome is ``won``."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM proposals WHERE outcome = 'won' ORDER BY created_at DESC"
        ).fetchall()
        return [Proposal.from_db_row(r) for r in rows]
