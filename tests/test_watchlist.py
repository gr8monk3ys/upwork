"""Tests for ``upwork_cli.watchlist``.

The persistence rule for a scoring run lives in ``upwork_cli.scoring`` and is
tested in ``test_scoring.py``. What is tested here is the cycle itself: which
Jobs count as new, which of them are worth an alert, and what happens when
scoring is unavailable or the search fails.

These reach the cycle through the module's interface rather than through
Click, which is what nothing could do while the cycle lived in a command
module -- and why a call inside it went wrong unnoticed.
"""

import pytest

from tests.fakes import FakeUpworkClient, job_node, job_search_payload
from upwork_cli import watchlist
from upwork_cli.config import Settings, save_settings
from upwork_cli.db import init_db
from upwork_cli.jobs import JobsError
from upwork_cli.models import JobPosting, ScoreResult


def _posting(job_id: str, title: str) -> JobPosting:
    return JobPosting(id=job_id, title=title, description="desc", skills=["Python"])


def _client(*job_ids: str) -> FakeUpworkClient:
    return FakeUpworkClient(
        search_results=job_search_payload(
            *(job_node(job_id, title=f"Job {job_id}") for job_id in job_ids)
        )
    )


class TestTerms:
    def test_normalize_collapses_whitespace(self):
        assert watchlist.normalize("  python   developer  ") == "python developer"

    def test_terms_are_normalized_and_deduplicated(self):
        settings = Settings(
            default_search_terms=[
                " python developer ",
                "python developer",
                "react native",
            ]
        )
        assert watchlist.terms(settings) == ["python developer", "react native"]

    def test_add_persists_the_normalized_term(self, isolated_config):
        settings = Settings()
        assert watchlist.add(settings, "  python   developer ") == "python developer"
        assert watchlist.terms(settings) == ["python developer"]

    def test_add_rejects_a_blank_term(self, isolated_config):
        with pytest.raises(watchlist.WatchlistError, match="cannot be empty"):
            watchlist.add(Settings(), "   ")

    def test_add_rejects_a_duplicate(self, isolated_config):
        settings = Settings(default_search_terms=["python"])
        with pytest.raises(watchlist.AlreadySaved, match="already exists"):
            watchlist.add(settings, "python")

    def test_remove_drops_the_term(self, isolated_config):
        settings = Settings(default_search_terms=["python", "rust"])
        assert watchlist.remove(settings, "python") == "python"
        assert watchlist.terms(settings) == ["rust"]

    def test_remove_rejects_an_unknown_term(self, isolated_config):
        with pytest.raises(watchlist.NotSaved, match="not found"):
            watchlist.remove(Settings(), "python")

    def test_add_leaves_the_rest_of_settings_alone(self, isolated_config):
        save_settings(Settings(min_score_threshold=9))
        watchlist.add(Settings(min_score_threshold=9), "python")
        from upwork_cli.config import load_settings

        assert load_settings().min_score_threshold == 9


class TestRunCycle:
    def test_new_jobs_alert_unscored_when_scoring_is_off(self, isolated_config):
        init_db()
        report = watchlist.run_cycle(_client("~a"), "python", scored=False)
        assert report.new_count == 1
        assert report.alert_count == 1
        assert report.alerts[0].score is None

    def test_only_jobs_at_or_above_min_score_alert(self, isolated_config, monkeypatch):
        init_db()
        results = [
            ScoreResult(job=_posting("~hot", "Hot"), score=8),
            ScoreResult(job=_posting("~cold", "Cold"), score=4),
        ]
        monkeypatch.setattr(watchlist, "score_jobs", lambda *a, **k: results)
        report = watchlist.run_cycle(
            _client("~hot", "~cold"), "python", min_score=7, scored=True
        )
        assert [r.job.id for r in report.alerts] == ["~hot"]

    def test_failed_scores_never_alert(self, isolated_config, monkeypatch):
        init_db()
        results = [ScoreResult(job=_posting("~bad", "Bad"), score=None, error="down")]
        monkeypatch.setattr(watchlist, "score_jobs", lambda *a, **k: results)
        report = watchlist.run_cycle(_client("~bad"), "python", scored=True)
        assert report.alerts == []
        assert report.new_count == 1

    def test_a_second_pass_finds_nothing_new(self, isolated_config):
        init_db()
        client = _client("~a")
        watchlist.run_cycle(client, "python")
        report = watchlist.run_cycle(client, "python")
        assert report.new_count == 0
        assert report.alert_count == 0

    def test_a_failed_search_raises_rather_than_reading_as_empty(self, isolated_config):
        init_db()

        class Broken(FakeUpworkClient):
            def search_jobs_graphql(self, *a, **k):
                raise RuntimeError("upstream 503")

        with pytest.raises(JobsError):
            watchlist.run_cycle(Broken(), "python")


class TestAlertText:
    def test_scored_alert_names_the_score(self):
        text = watchlist.alert_text(ScoreResult(job=_posting("~a", "Build"), score=9))
        assert text == "[Score 9] Build"

    def test_unscored_alert_says_so(self):
        assert watchlist.alert_text(ScoreResult(job=_posting("~a", "Build"))) == (
            "[Score ?] Build"
        )

    def test_untitled_job_still_alerts(self):
        assert "Untitled" in watchlist.alert_text(
            ScoreResult(job=JobPosting(id="~a", title=""))
        )


class TestSendDiscord:
    def test_non_https_webhook_is_refused(self):
        with pytest.raises(watchlist.WatchlistError, match="https://"):
            watchlist.send_discord("http://example.com/hook", "hi")

    def test_a_failed_post_raises(self, monkeypatch):
        def boom(_request):
            raise OSError("connection refused")

        monkeypatch.setattr(watchlist.urllib.request, "urlopen", boom)
        with pytest.raises(watchlist.WatchlistError, match="connection refused"):
            watchlist.send_discord("https://example.com/hook", "hi")
