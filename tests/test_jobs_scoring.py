"""Tests for the alert filtering around a scoring run.

The persistence rule itself lives in ``upwork_cli.scoring`` and is tested in
``test_scoring.py``. What is left here is the alert path's own behavior:
which scored jobs are worth interrupting the user for, and what happens when
scoring is unavailable.
"""

from types import SimpleNamespace
from unittest.mock import patch

from tests.fakes import FakeUpworkClient, job_node, job_search_payload
from upwork_cli.commands.jobs import _run_search_cycle, _score_alert_jobs
from upwork_cli.db import init_db
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
        )

        assert result == [ScoreResult(job=jobs[0])]
        assert result[0].score is None


class TestRunSearchCycle:
    """The composition around ``_score_alert_jobs``.

    Nothing exercised this before, and the call inside it had been passing
    the wrong arguments since #31: every alert path raised ``TypeError`` the
    moment a search returned a new Job.
    """

    def _client(self):
        return FakeUpworkClient(
            search_results=job_search_payload(job_node("~new", title="New Job"))
        )

    def _settings(self):
        return SimpleNamespace(discord_webhook_url="", default_search_terms=[])

    def test_cycle_reports_new_jobs_without_scoring(self):
        init_db()
        new_count, alert_count = _run_search_cycle(
            self._client(),
            self._settings(),
            query="python",
            limit=5,
            min_score=7,
            notify="terminal",
            has_scoring=False,
            profile_summary="",
        )
        assert (new_count, alert_count) == (1, 1)

    def test_cycle_alerts_only_above_threshold(self):
        init_db()
        results = [ScoreResult(job=_posting("~new", "New Job"), score=9)]
        with patch("upwork_cli.commands.jobs.score_jobs", return_value=results):
            new_count, alert_count = _run_search_cycle(
                self._client(),
                self._settings(),
                query="python",
                limit=5,
                min_score=7,
                notify="terminal",
                has_scoring=True,
                profile_summary="profile",
            )
        assert (new_count, alert_count) == (1, 1)

    def test_cycle_is_quiet_when_nothing_is_new(self):
        init_db()
        client = self._client()
        settings = self._settings()
        _run_search_cycle(
            client,
            settings,
            query="python",
            limit=5,
            min_score=7,
            notify="terminal",
            has_scoring=False,
            profile_summary="",
        )
        # Second pass: the same posting has been seen, so nothing is new.
        assert _run_search_cycle(
            client,
            settings,
            query="python",
            limit=5,
            min_score=7,
            notify="terminal",
            has_scoring=False,
            profile_summary="",
        ) == (0, 0)
