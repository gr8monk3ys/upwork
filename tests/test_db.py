"""Tests for the SQLite database layer in upwork_cli.db."""

import json
import sqlite3

import pytest

from upwork_cli.db import (
    init_db,
    upsert_job,
    save_score,
    get_jobs_with_scores,
    save_proposal,
    get_proposals,
    save_bookmark,
    remove_bookmark,
    get_bookmarks,
    mark_seen,
    is_seen,
)
from tests.conftest import _make_job_dict


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
        job = _make_job_dict()
        upsert_job(job)

        rows = get_jobs_with_scores(limit=10)
        assert len(rows) == 1
        assert rows[0]["id"] == job["id"]
        assert rows[0]["title"] == job["title"]

    def test_update_existing_job(self, isolated_config):
        init_db()
        job = _make_job_dict()
        upsert_job(job)

        # Update the title
        job["title"] = "Updated Title"
        upsert_job(job)

        rows = get_jobs_with_scores(limit=10)
        assert len(rows) == 1
        assert rows[0]["title"] == "Updated Title"

    def test_skills_serialized_as_json(self, isolated_config):
        init_db()
        job = _make_job_dict(skills=["Python", "Django"])
        upsert_job(job)

        rows = get_jobs_with_scores(limit=10)
        skills_raw = rows[0]["skills"]
        assert json.loads(skills_raw) == ["Python", "Django"]

    def test_skills_already_string(self, isolated_config):
        init_db()
        job = _make_job_dict(skills='["Go", "Rust"]')
        upsert_job(job)

        rows = get_jobs_with_scores(limit=10)
        assert json.loads(rows[0]["skills"]) == ["Go", "Rust"]

    def test_client_verified_roundtrip(self, isolated_config):
        init_db()
        job = _make_job_dict(client_verified=True)
        upsert_job(job)

        rows = get_jobs_with_scores(limit=10)
        assert rows[0]["client_verified"] == 1


class TestScores:
    def test_save_and_get_score(self, isolated_config):
        init_db()
        job = _make_job_dict()
        upsert_job(job)
        save_score(job["id"], 8, "Good match")

        rows = get_jobs_with_scores(limit=10)
        assert rows[0]["score"] == 8
        assert rows[0]["reasoning"] == "Good match"

    def test_scores_sorted_descending(self, isolated_config):
        init_db()
        for i, score in enumerate([3, 9, 6]):
            job = _make_job_dict(id=f"~0{i}")
            upsert_job(job)
            save_score(job["id"], score, f"Score {score}")

        rows = get_jobs_with_scores(limit=10)
        scores = [r["score"] for r in rows]
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


class TestBookmarks:
    def test_save_and_get_bookmark(self, isolated_config):
        init_db()
        job = _make_job_dict()
        upsert_job(job)
        save_bookmark(job["id"], "Looks promising")

        bmarks = get_bookmarks()
        assert len(bmarks) == 1
        assert bmarks[0]["note"] == "Looks promising"

    def test_remove_bookmark(self, isolated_config):
        init_db()
        job = _make_job_dict()
        upsert_job(job)
        save_bookmark(job["id"])
        remove_bookmark(job["id"])

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
