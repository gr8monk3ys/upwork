"""Tests for the alert filtering around a scoring run.

The persistence rule itself lives in ``upwork_cli.scoring`` and is tested in
``test_scoring.py``. What is left here is the alert path's own behavior:
which scored jobs are worth interrupting the user for, and what happens when
scoring is unavailable.
"""

from unittest.mock import patch

from upwork_cli.commands.jobs import _score_alert_jobs
from upwork_cli.models import JobPosting, ScoreResult


def _posting(job_id: str, title: str) -> JobPosting:
    return JobPosting(id=job_id, title=title, description="desc", skills=["Python"])


class TestScoreAlertJobs:
    def test_only_jobs_at_or_above_min_score_alert(self):
        jobs = [_posting("hot", "Hot"), _posting("cold", "Cold")]
        results = [
            ScoreResult(job=jobs[0], score=8, reasoning="Great."),
            ScoreResult(job=jobs[1], score=4, reasoning="Meh."),
        ]
        with patch("upwork_cli.commands.jobs.score_jobs", return_value=results):
            hot = _score_alert_jobs(
                jobs,
                min_score=7,
                has_scoring=True,
                profile_summary="profile",
                api_key="key",
            )

        assert [r.job.id for r in hot] == ["hot"]

    def test_failed_scores_never_alert(self):
        jobs = [_posting("bad", "Bad")]
        results = [ScoreResult(job=jobs[0], score=None, error="API down")]
        with patch("upwork_cli.commands.jobs.score_jobs", return_value=results):
            hot = _score_alert_jobs(
                jobs,
                min_score=7,
                has_scoring=True,
                profile_summary="profile",
                api_key="key",
            )

        assert hot == []

    def test_without_scoring_every_job_alerts_unscored(self):
        """No API key or no profile: still surface the jobs, without a score."""
        jobs = [_posting("a", "A")]
        result = _score_alert_jobs(
            jobs,
            min_score=7,
            has_scoring=False,
            profile_summary="",
            api_key="",
        )

        assert result == [ScoreResult(job=jobs[0])]
        assert result[0].score is None
