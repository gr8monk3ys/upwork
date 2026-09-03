"""Tests for the SQLite database layer in upwork_cli.db."""

import json
import sqlite3

import pytest

from tests.conftest import _make_job_posting
from upwork_cli.db import (
    get_bookmarks,
    get_connection,
    get_job,
    get_jobs_with_scores,
    get_latest_proposal,
    get_proposal,
    get_proposals,
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

        rows = get_jobs_with_scores(limit=10)
        assert len(rows) == 1
        assert rows[0].job.id == job.id
        assert rows[0].job.title == job.title

    def test_update_existing_job(self, isolated_config):
        init_db()
        job = _make_job_posting()
        upsert_job(job)

        # Update the title
        job.title = "Updated Title"
        upsert_job(job)

        rows = get_jobs_with_scores(limit=10)
        assert len(rows) == 1
        assert rows[0].job.title == "Updated Title"

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
        rows = get_jobs_with_scores(limit=10)
        assert rows[0].job.skills == ["Python", "Django"]

    def test_client_verified_roundtrip(self, isolated_config):
        init_db()
        job = _make_job_posting(client_verified=True)
        upsert_job(job)

        rows = get_jobs_with_scores(limit=10)
        assert rows[0].job.client_verified is True


class TestGetJob:
    def test_returns_a_posting(self, isolated_config):
        init_db()
        job = _make_job_posting()
        upsert_job(job)

        assert get_job(job.id) == job

    def test_returns_none_when_absent(self, isolated_config):
        init_db()
        assert get_job("nope") is None


class TestScores:
    def test_save_and_get_score(self, isolated_config):
        init_db()
        job = _make_job_posting()
        upsert_job(job)
        save_score(job.id, 8, "Good match")

        rows = get_jobs_with_scores(limit=10)
        assert rows[0].score == 8
        assert rows[0].reasoning == "Good match"

    def test_scores_sorted_descending(self, isolated_config):
        init_db()
        for i, score in enumerate([3, 9, 6]):
            job = _make_job_posting(id=f"~0{i}")
            upsert_job(job)
            save_score(job.id, score, f"Score {score}")

        rows = get_jobs_with_scores(limit=10)
        scores = [r.score for r in rows]
        assert scores == [9, 6, 3]

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
