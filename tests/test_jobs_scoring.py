"""Tests that failed AI scores are never persisted as real scores."""

from unittest.mock import patch

from tests.conftest import _make_job_posting
from upwork_cli.commands.jobs import _score_alert_jobs
from upwork_cli.db import get_connection, init_db, upsert_job
from upwork_cli.models import JobPosting


def _posting(job_id: str, title: str) -> JobPosting:
    return JobPosting(id=job_id, title=title, description="desc", skills=["Python"])


class TestScoreAlertJobs:
    def test_failed_scores_not_saved(self, isolated_config):
        init_db()
        upsert_job(_make_job_posting(id="ok-job"))
        upsert_job(_make_job_posting(id="bad-job"))

        scored = [
            {"id": "ok-job", "title": "OK", "score": 8, "reasoning": "Good."},
            {"id": "bad-job", "title": "Bad", "score": None, "error": "API down"},
        ]
        with patch("upwork_cli.commands.jobs.score_jobs_batch", return_value=scored):
            hot = _score_alert_jobs(
                [_posting("ok-job", "OK"), _posting("bad-job", "Bad")],
                min_score=7,
                has_scoring=True,
                profile_summary="profile",
                api_key="key",
            )

        # Only the successful score is alert-worthy and persisted.
        assert [item["id"] for item in hot] == ["ok-job"]
        with get_connection() as conn:
            rows = conn.execute("SELECT job_id, score FROM scores").fetchall()
        assert {(r["job_id"], r["score"]) for r in rows} == {("ok-job", 8)}

    def test_no_scoring_returns_placeholders(self, isolated_config):
        init_db()
        result = _score_alert_jobs(
            [_posting("a", "A")],
            min_score=7,
            has_scoring=False,
            profile_summary="",
            api_key="",
        )
        assert result == [{"id": "a", "title": "A", "score": "?"}]
