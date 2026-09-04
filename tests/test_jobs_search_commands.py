"""Tests for the saved-search and watch commands.

`watchlist` is tested through its own interface in test_watchlist.py. What
these cover is the command layer around it: the guards in `_prepare_run`,
the rendering in `_cycle`, and the two watch loops -- which had no coverage
at all, and which is where the TypeError fixed in #33 had been sitting.
"""

import pytest
from click.testing import CliRunner

from tests.fakes import FakeUpworkClient, job_node, job_search_payload
from upwork_cli.cli import cli
from upwork_cli.config import Profile, Settings, save_profile, save_settings
from upwork_cli.db import init_db


@pytest.fixture
def runner():
    return CliRunner(env={"COLUMNS": "200"})


@pytest.fixture
def authed(monkeypatch):
    """A client behind the single construction site, with one job to find."""
    client = FakeUpworkClient(
        search_results=job_search_payload(job_node("~new", title="Build a scraper"))
    )
    monkeypatch.setattr("upwork_cli.commands.jobs.get_client", lambda: client)
    return client


def _saved(*terms: str) -> None:
    save_settings(Settings(default_search_terms=list(terms)))


class TestSavedSearchTerms:
    def test_add_list_remove_round_trip(self, runner, isolated_config):
        assert (
            "Added" in runner.invoke(cli, ["jobs", "searches", "add", "python"]).output
        )
        listed = runner.invoke(cli, ["jobs", "searches", "list"])
        assert "python" in listed.output
        assert (
            "Removed"
            in runner.invoke(cli, ["jobs", "searches", "remove", "python"]).output
        )
        assert (
            "No saved search terms yet"
            in runner.invoke(cli, ["jobs", "searches", "list"]).output
        )

    def test_adding_a_duplicate_warns_and_exits_zero(self, runner, isolated_config):
        _saved("python")
        result = runner.invoke(cli, ["jobs", "searches", "add", "python"])
        assert result.exit_code == 0
        assert "already exists" in result.output

    def test_removing_an_unknown_term_warns_and_exits_zero(
        self, runner, isolated_config
    ):
        result = runner.invoke(cli, ["jobs", "searches", "remove", "nope"])
        assert result.exit_code == 0
        assert "not found" in result.output

    def test_a_blank_term_is_refused(self, runner, isolated_config):
        result = runner.invoke(cli, ["jobs", "searches", "add", "   "])
        assert result.exit_code == 1
        assert "cannot be empty" in result.output


class TestSavedSearchRun:
    def test_no_saved_terms_fails_with_a_hint(self, runner, isolated_config):
        init_db()
        result = runner.invoke(cli, ["jobs", "searches", "run"])
        assert result.exit_code == 1
        assert "No saved search terms configured" in result.output
        assert "searches add" in result.output

    def test_discord_without_a_webhook_fails(self, runner, isolated_config):
        init_db()
        _saved("python")
        result = runner.invoke(cli, ["jobs", "searches", "run", "--notify", "discord"])
        assert result.exit_code == 1
        assert "Discord webhook URL not configured" in result.output

    def test_a_run_reports_new_jobs(self, runner, isolated_config, authed):
        init_db()
        _saved("scraper")
        result = runner.invoke(cli, ["jobs", "searches", "run"])
        assert result.exit_code == 0, result.output
        assert "1 new job(s) found" in result.output

    def test_scoring_disabled_is_announced_once(self, runner, isolated_config, authed):
        init_db()
        _saved("scraper")
        result = runner.invoke(cli, ["jobs", "searches", "run"])
        assert "Scoring disabled" in result.output

    def test_a_second_run_finds_nothing_new(self, runner, isolated_config, authed):
        init_db()
        _saved("scraper")
        runner.invoke(cli, ["jobs", "searches", "run"])
        result = runner.invoke(cli, ["jobs", "searches", "run"])
        assert "No new jobs found across saved searches" in result.output

    def test_a_failed_search_warns_and_the_run_continues(
        self, runner, isolated_config, monkeypatch
    ):
        init_db()
        _saved("scraper")
        monkeypatch.setattr(
            "upwork_cli.commands.jobs.get_client",
            lambda: FakeUpworkClient(search_results=RuntimeError("upstream 503")),
        )
        result = runner.invoke(cli, ["jobs", "searches", "run"])
        assert result.exit_code == 0
        assert "API search failed" in result.output

    def test_unauthenticated_fails_before_searching(self, runner, isolated_config):
        init_db()
        _saved("scraper")
        result = runner.invoke(cli, ["jobs", "searches", "run"])
        assert result.exit_code == 1
        assert "Not authenticated" in result.output


class TestWatchLoops:
    """Both loops run one cycle then sleep; interrupting the sleep is how a
    test gets exactly one pass without waiting for it."""

    def _one_pass(self, monkeypatch):
        def stop(_seconds):
            raise KeyboardInterrupt

        monkeypatch.setattr("upwork_cli.commands.jobs.time.sleep", stop)

    def test_jobs_watch_runs_a_cycle_then_stops_cleanly(
        self, runner, isolated_config, authed, monkeypatch
    ):
        init_db()
        self._one_pass(monkeypatch)
        result = runner.invoke(cli, ["jobs", "watch", "scraper"])
        assert result.exit_code == 0, result.output
        assert "Watching for:" in result.output
        assert "1 new job(s) found" in result.output
        assert "Watch stopped" in result.output

    def test_saved_search_watch_runs_a_cycle_then_stops_cleanly(
        self, runner, isolated_config, authed, monkeypatch
    ):
        init_db()
        _saved("scraper")
        self._one_pass(monkeypatch)
        result = runner.invoke(cli, ["jobs", "searches", "watch"])
        assert result.exit_code == 0, result.output
        assert "Watching 1 saved search(es)" in result.output
        assert "Saved-search watch stopped" in result.output

    def test_jobs_watch_with_scoring_enabled_scores_the_new_jobs(
        self, runner, isolated_config, authed, monkeypatch, use_completer
    ):
        from tests.fakes import FakeCompleter

        init_db()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
        save_profile(Profile(title="Python dev", skills=["Python"]))
        use_completer(FakeCompleter('{"score": 9, "reasoning": "Strong."}'))
        self._one_pass(monkeypatch)
        result = runner.invoke(cli, ["jobs", "watch", "scraper", "--min-score", "7"])
        assert result.exit_code == 0, result.output
        assert "Score 9" in result.output
