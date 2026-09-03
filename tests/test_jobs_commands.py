"""Characterization tests for ``jobs score`` and ``jobs detail``.

These two commands rehydrate a ``JobPosting`` from a database row by hand and
had no coverage at all. The tests below pin down what they do today so the
hydration can be moved behind ``JobPosting.from_db_row`` without changing
observable behavior.

Rows are seeded with raw SQL on purpose: the seeding must stay valid across a
refactor that changes ``upsert_job``'s interface, so it depends only on the
schema.

The scorer is patched at ``upwork_cli.scoring`` -- where it is imported, not
where it is defined. That target moves whenever the call moves, which is the
cost of mocking an import site rather than an interface.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from upwork_cli.cli import cli
from upwork_cli.config import Profile, save_profile
from upwork_cli.db import get_connection, init_db


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")


@pytest.fixture
def profile():
    save_profile(Profile(title="Python Developer", skills=["Python", "FastAPI"]))


def _seed_job(job_id: str = "~01abc123", **overrides) -> dict:
    """Insert a job row directly, bypassing the module under refactor."""
    row = {
        "id": job_id,
        "title": "Python Developer Needed",
        "description": "Build a REST API using FastAPI.",
        "skills": json.dumps(["Python", "FastAPI", "PostgreSQL"]),
        "budget_amount": 5000.0,
        "budget_currency": "USD",
        "duration": "1 to 3 months",
        "engagement": "30+ hrs/week",
        "client_country": "United States",
        "client_total_spent": 150000.0,
        "client_total_hires": 42,
        "client_feedback": 4.9,
        "client_verified": 1,
        "created_at": "2025-01-15T10:00:00Z",
    }
    row.update(overrides)
    with get_connection() as conn:
        conn.execute(
            f"""INSERT OR REPLACE INTO jobs ({", ".join(row)})
            VALUES ({", ".join("?" * len(row))})""",
            tuple(row.values()),
        )
    return row


def _seed_score(job_id: str, score: int, reasoning: str = "Prior score") -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO scores (job_id, score, reasoning) VALUES (?, ?, ?)",
            (job_id, score, reasoning),
        )


def _saved_scores() -> dict[str, int]:
    with get_connection() as conn:
        rows = conn.execute("SELECT job_id, score FROM scores").fetchall()
    return {r["job_id"]: r["score"] for r in rows}


class TestJobsScore:
    def test_scores_unscored_jobs_and_persists_them(
        self, runner, isolated_config, api_key, profile
    ):
        init_db()
        _seed_job("job-a", title="Job A")

        scored = [
            {"id": "job-a", "title": "Job A", "score": 8, "reasoning": "Good fit"}
        ]
        with patch("upwork_cli.scoring.score_jobs_batch", return_value=scored) as batch:
            result = runner.invoke(cli, ["jobs", "score"])

        assert result.exit_code == 0
        assert _saved_scores() == {"job-a": 8}
        assert "Good fit" in result.output

        # The scorer receives the job summary built from the stored row.
        sent = batch.call_args[0][0]
        assert [item["id"] for item in sent] == ["job-a"]
        assert "Job A" in sent[0]["summary"]

    def test_skills_reach_the_scorer_decoded(
        self, runner, isolated_config, api_key, profile
    ):
        """The stored ``skills`` column is JSON text; the summary must not show it."""
        init_db()
        _seed_job("job-a")

        with patch("upwork_cli.scoring.score_jobs_batch", return_value=[]) as batch:
            runner.invoke(cli, ["jobs", "score"])

        summary = batch.call_args[0][0][0]["summary"]
        assert "Skills: Python, FastAPI, PostgreSQL" in summary
        assert "[" not in summary.split("Skills:")[1].splitlines()[0]

    def test_failed_scores_are_not_persisted(
        self, runner, isolated_config, api_key, profile
    ):
        init_db()
        _seed_job("ok-job", title="OK")
        _seed_job("bad-job", title="Bad")

        scored = [
            {"id": "ok-job", "title": "OK", "score": 8, "reasoning": "Good."},
            {"id": "bad-job", "title": "Bad", "score": None, "error": "API down"},
        ]
        with patch("upwork_cli.scoring.score_jobs_batch", return_value=scored):
            result = runner.invoke(cli, ["jobs", "score"])

        assert result.exit_code == 0
        assert _saved_scores() == {"ok-job": 8}

    def test_already_scored_jobs_are_skipped(
        self, runner, isolated_config, api_key, profile
    ):
        init_db()
        _seed_job("scored-job")
        _seed_score("scored-job", 7)

        with patch("upwork_cli.scoring.score_jobs_batch") as batch:
            result = runner.invoke(cli, ["jobs", "score"])

        batch.assert_not_called()
        assert "No unscored jobs found" in result.output
        assert result.exit_code == 0

    def test_missing_api_key_reports_and_exits_zero(
        self, runner, isolated_config, profile
    ):
        init_db()
        _seed_job()
        result = runner.invoke(cli, ["jobs", "score"])
        assert "Anthropic API key not configured" in result.output
        assert result.exit_code == 0

    def test_empty_profile_reports_and_exits_zero(
        self, runner, isolated_config, api_key
    ):
        init_db()
        _seed_job()
        result = runner.invoke(cli, ["jobs", "score"])
        assert "Profile is empty" in result.output
        assert result.exit_code == 0


class TestJobsDetail:
    def test_falls_back_to_cache_when_unauthenticated(self, runner, isolated_config):
        init_db()
        _seed_job("~01abc123")

        result = runner.invoke(cli, ["jobs", "detail", "~01abc123"])

        assert result.exit_code == 0
        assert "Python Developer Needed" in result.output
        assert "$5,000 USD" in result.output
        assert "1 to 3 months" in result.output
        assert "30+ hrs/week" in result.output
        assert "United States" in result.output
        assert "Build a REST API using FastAPI." in result.output

    def test_skills_render_decoded(self, runner, isolated_config):
        init_db()
        _seed_job("~01abc123")
        result = runner.invoke(cli, ["jobs", "detail", "~01abc123"])
        assert "Python, FastAPI, PostgreSQL" in result.output

    def test_client_verified_renders_as_yes(self, runner, isolated_config):
        init_db()
        _seed_job("~01abc123", client_verified=1)
        result = runner.invoke(cli, ["jobs", "detail", "~01abc123"])
        assert "Verified: Yes" in result.output

    def test_client_unverified_renders_as_no(self, runner, isolated_config):
        init_db()
        _seed_job("~01abc123", client_verified=0)
        result = runner.invoke(cli, ["jobs", "detail", "~01abc123"])
        assert "Verified: No" in result.output

    def test_missing_job_reports_and_exits_zero(self, runner, isolated_config):
        init_db()
        result = runner.invoke(cli, ["jobs", "detail", "nope"])
        assert "not found in API or local cache" in result.output
        assert result.exit_code == 0

    def test_api_result_preferred_over_cache(self, runner, isolated_config):
        init_db()
        _seed_job("~01abc123", title="Stale Cached Title")

        client = MagicMock()
        client.is_authenticated = True
        client.get_job_detail.return_value = {
            "id": "~01abc123",
            "title": "Fresh API Title",
            "snippet": "From the API.",
        }
        with patch("upwork_cli.commands.jobs.UpworkClient", return_value=client):
            result = runner.invoke(cli, ["jobs", "detail", "~01abc123"])

        assert "Fresh API Title" in result.output
        assert "Stale Cached Title" not in result.output
