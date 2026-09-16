"""Tests for the scoring run in upwork_cli.scoring.

This is where the rule that a failed attempt is never persisted lives, so
this is where it is tested -- once, rather than in each command that scores.
"""

from unittest.mock import patch

from upwork_cli.db import get_connection, init_db, upsert_job
from upwork_cli.models import JobPosting, ScoreResult
from upwork_cli.scoring import score_jobs


def _posting(job_id: str, title: str = "A Job") -> JobPosting:
    return JobPosting(id=job_id, title=title, description="desc", skills=["Python"])


def _saved_scores() -> dict[str, int]:
    with get_connection() as conn:
        rows = conn.execute("SELECT job_id, score FROM scores").fetchall()
    return {r["job_id"]: r["score"] for r in rows}


class TestScoreJobs:
    def test_persists_successful_scores(self, isolated_config):
        init_db()
        upsert_job(_posting("ok"))

        batch = [{"id": "ok", "title": "A Job", "score": 8, "reasoning": "Good fit"}]
        with patch("upwork_cli.scoring.score_jobs_batch", return_value=batch):
            results = score_jobs([_posting("ok")], "profile", "key")

        assert _saved_scores() == {"ok": 8}
        assert results == [
            ScoreResult(job=_posting("ok"), score=8, reasoning="Good fit")
        ]

    def test_failed_attempts_are_returned_but_never_persisted(self, isolated_config):
        """A transient API failure must not bury the job at a missing score."""
        init_db()
        upsert_job(_posting("ok"))
        upsert_job(_posting("bad"))

        batch = [
            {"id": "ok", "title": "A Job", "score": 8, "reasoning": "Good."},
            {"id": "bad", "title": "A Job", "score": None, "error": "API down"},
        ]
        with patch("upwork_cli.scoring.score_jobs_batch", return_value=batch):
            results = score_jobs([_posting("ok"), _posting("bad")], "profile", "key")

        assert _saved_scores() == {"ok": 8}
        failed = [r for r in results if r.score is None]
        assert [r.job.id for r in failed] == ["bad"]
        assert failed[0].error == "API down"

    def test_carries_the_posting_through(self, isolated_config):
        """Callers render budgets off the result, so the job must come back."""
        init_db()
        job = JobPosting(id="j", title="T", budget_amount=5000.0, budget_currency="EUR")
        upsert_job(job)

        batch = [{"id": "j", "score": 7, "reasoning": "ok"}]
        with patch("upwork_cli.scoring.score_jobs_batch", return_value=batch):
            results = score_jobs([job], "profile", "key")

        assert results[0].job.budget_amount == 5000.0
        assert results[0].job.budget_currency == "EUR"

    def test_summaries_are_built_from_the_posting(self, isolated_config):
        init_db()
        job = _posting("j")
        upsert_job(job)

        with patch("upwork_cli.scoring.score_jobs_batch", return_value=[]) as batch:
            score_jobs([job], "profile summary", "key", model="claude-x")

        sent, profile_summary, api_key = batch.call_args[0]
        assert sent == [{"id": "j", "title": "A Job", "summary": job.summary_for_ai()}]
        assert profile_summary == "profile summary"
        assert api_key == "key"
        assert batch.call_args[1]["model"] == "claude-x"

    def test_no_jobs_does_not_call_the_scorer(self, isolated_config):
        init_db()
        with patch("upwork_cli.scoring.score_jobs_batch") as batch:
            assert score_jobs([], "profile", "key") == []
        batch.assert_not_called()

    def test_ignores_results_for_unknown_jobs(self, isolated_config):
        """The scorer echoes its input back; a stray id must not crash rendering."""
        init_db()
        upsert_job(_posting("known"))

        batch = [
            {"id": "known", "score": 5, "reasoning": "ok"},
            {"id": "ghost", "score": 9, "reasoning": "not ours"},
        ]
        with patch("upwork_cli.scoring.score_jobs_batch", return_value=batch):
            results = score_jobs([_posting("known")], "profile", "key")

        assert [r.job.id for r in results] == ["known"]
