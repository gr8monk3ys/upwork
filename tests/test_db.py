"""Tests for the SQLite database layer in upwork_cli.db."""

import json
import sqlite3

import pytest

from tests.conftest import _make_job_posting
from upwork_cli.db import (
    get_bookmarks,
    get_connection,
    get_job,
    get_latest_proposal,
    get_proposal,
    get_proposals,
    get_unscored_jobs,
    init_db,
    is_seen,
    mark_seen,
    remove_bookmark,
    save_bookmark,
    save_proposal,
    save_score,
    upsert_job,
)


class TestInitDb:
    def test_creates_tables(self, isolated_config):
        init_db()
        # A second call should not raise (IF NOT EXISTS)
        init_db()

    def test_jobs_table_exists(self, isolated_config):
        from upwork_cli.db import get_connection

        init_db()
        with get_connection() as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'"
            ).fetchone()
            assert row is not None


class TestUpsertJob:
    def test_insert_new_job(self, isolated_config):
        init_db()
        job = _make_job_posting()
        upsert_job(job)

        stored = get_job(job.id)
        assert stored is not None
        assert stored.id == job.id
        assert stored.title == job.title

    def test_update_existing_job(self, isolated_config):
        init_db()
        job = _make_job_posting()
        upsert_job(job)

        # Update the title
        job.title = "Updated Title"
        upsert_job(job)

        assert get_job(job.id).title == "Updated Title"

    def test_skills_serialized_as_json(self, isolated_config):
        init_db()
        job = _make_job_posting(skills=["Python", "Django"])
        upsert_job(job)

        # stored as JSON text ...
        with get_connection() as conn:
            raw = conn.execute(
                "SELECT skills FROM jobs WHERE id = ?", (job.id,)
            ).fetchone()
        assert json.loads(raw["skills"]) == ["Python", "Django"]

        # ... and handed back as a list
        assert get_job(job.id).skills == ["Python", "Django"]

    def test_client_verified_roundtrip(self, isolated_config):
        init_db()
        job = _make_job_posting(client_verified=True)
        upsert_job(job)

        assert get_job(job.id).client_verified is True


class TestGetJob:
    def test_returns_a_posting(self, isolated_config):
        init_db()
        job = _make_job_posting()
        upsert_job(job)

        assert get_job(job.id) == job

    def test_returns_none_when_absent(self, isolated_config):
        init_db()
        assert get_job("nope") is None


class TestGetUnscoredJobs:
    def test_returns_only_unscored(self, isolated_config):
        init_db()
        scored, unscored = _make_job_posting(id="s1"), _make_job_posting(id="u1")
        upsert_job(scored)
        upsert_job(unscored)
        save_score("s1", 7, "fine")

        assert [j.id for j in get_unscored_jobs()] == ["u1"]

    def test_reaches_unscored_jobs_beyond_the_limit_window(self, isolated_config):
        """Regression: unscored jobs sort last, so filtering after a LIMIT
        stranded every unscored job once the cache held more than `limit`."""
        init_db()
        for i in range(45):
            upsert_job(_make_job_posting(id=f"s{i}"))
            save_score(f"s{i}", 5, "x")
        for i in range(15):
            upsert_job(_make_job_posting(id=f"u{i}"))

        # 45 scored + 15 unscored = 60 rows; a window of 50 must still see all 15.
        assert len(get_unscored_jobs(limit=50)) == 15

    def test_respects_its_limit(self, isolated_config):
        init_db()
        for i in range(5):
            upsert_job(_make_job_posting(id=f"u{i}"))
        assert len(get_unscored_jobs(limit=3)) == 3

    def test_empty_when_everything_is_scored(self, isolated_config):
        init_db()
        job = _make_job_posting()
        upsert_job(job)
        save_score(job.id, 9, "great")
        assert get_unscored_jobs() == []


class TestScores:
    def test_save_and_get_score(self, isolated_config):
        init_db()
        job = _make_job_posting()
        upsert_job(job)
        save_score(job.id, 8, "Good match")

        with get_connection() as conn:
            row = conn.execute(
                "SELECT score, reasoning FROM scores WHERE job_id = ?", (job.id,)
            ).fetchone()
        assert row["score"] == 8
        assert row["reasoning"] == "Good match"

    def test_rescoring_replaces_the_previous_score(self, isolated_config):
        init_db()
        job = _make_job_posting()
        upsert_job(job)
        save_score(job.id, 4, "First pass")
        save_score(job.id, 9, "Second pass")

        with get_connection() as conn:
            rows = conn.execute(
                "SELECT score FROM scores WHERE job_id = ?", (job.id,)
            ).fetchall()
        assert [r["score"] for r in rows] == [9]

    def test_score_requires_existing_job(self, isolated_config):
        init_db()
        with pytest.raises(sqlite3.IntegrityError):
            save_score("~missing", 8, "Should fail")


class TestProposals:
    def test_save_and_get_proposal(self, isolated_config):
        init_db()
        pid = save_proposal("~01abc", "Test Job", "My proposal.", "professional")
        assert pid > 0

        proposals = get_proposals(limit=10)
        assert len(proposals) == 1
        assert proposals[0]["content"] == "My proposal."

    def test_proposals_ordered_desc(self, isolated_config):
        init_db()
        save_proposal("~01a", "Job A", "First", "casual")
        save_proposal("~01b", "Job B", "Second", "technical")

        proposals = get_proposals(limit=10)
        assert len(proposals) == 2
        contents = {p["content"] for p in proposals}
        assert contents == {"First", "Second"}


class TestProposalLookup:
    def test_get_proposal_by_id(self, isolated_config):
        init_db()
        job = _make_job_posting()
        upsert_job(job)
        pid = save_proposal(job.id, job.title, "Cover letter body")

        found = get_proposal(pid)
        assert found is not None
        assert found["content"] == "Cover letter body"

    def test_get_proposal_returns_none_when_absent(self, isolated_config):
        init_db()
        assert get_proposal(999) is None

    def test_latest_proposal_is_the_most_recent(self, isolated_config):
        init_db()
        job = _make_job_posting()
        upsert_job(job)
        save_proposal(job.id, job.title, "older")
        with get_connection() as conn:
            conn.execute(
                "UPDATE proposals SET created_at = '2020-01-01' WHERE content = 'older'"
            )
        save_proposal(job.id, job.title, "newer")

        latest = get_latest_proposal()
        assert latest is not None
        assert latest["content"] == "newer"

    def test_latest_proposal_none_when_empty(self, isolated_config):
        init_db()
        assert get_latest_proposal() is None


class TestBookmarks:
    def test_save_and_get_bookmark(self, isolated_config):
        init_db()
        job = _make_job_posting()
        upsert_job(job)
        save_bookmark(job.id, "Looks promising")

        bmarks = get_bookmarks()
        assert len(bmarks) == 1
        assert bmarks[0]["note"] == "Looks promising"

    def test_remove_bookmark(self, isolated_config):
        init_db()
        job = _make_job_posting()
        upsert_job(job)
        save_bookmark(job.id)
        remove_bookmark(job.id)

        assert get_bookmarks() == []


class TestWatchSeen:
    def test_mark_and_check_seen(self, isolated_config):
        init_db()
        assert is_seen("~01xyz") is False
        mark_seen("~01xyz", "python")
        assert is_seen("~01xyz") is True

    def test_mark_seen_idempotent(self, isolated_config):
        init_db()
        mark_seen("~01xyz", "python")
        mark_seen("~01xyz", "python")  # INSERT OR IGNORE
        assert is_seen("~01xyz") is True
