"""Rendering tests for the pipeline dashboard.

The module behind these is tested in test_pipeline_module.py. What is left
here is what the command actually puts on screen -- the populated tables,
which had no coverage because every existing test used an empty Pipeline.
"""

import pytest
from click.testing import CliRunner

from upwork_cli import pipeline as pipeline_api
from upwork_cli.cli import cli
from upwork_cli.db import init_db, upsert_job
from upwork_cli.models import JobPosting


@pytest.fixture
def runner():
    return CliRunner(env={"COLUMNS": "200"})


def _job(job_id: str, title: str, stage: str, **kw) -> JobPosting:
    posting = JobPosting(id=job_id, title=title, **kw)
    upsert_job(posting)
    pipeline_api.move(job_id, stage)
    return posting


class TestView:
    def test_lists_jobs_with_their_stage_and_budget(self, runner, isolated_config):
        init_db()
        _job("~a", "Build an API", "applied", budget_amount=3000.0)
        result = runner.invoke(cli, ["pipeline", "view"])
        assert result.exit_code == 0
        assert "Build an API" in result.output
        assert "applied" in result.output
        assert "3,000.00" in result.output
        assert "1 job(s) shown" in result.output

    def test_filters_to_one_stage(self, runner, isolated_config):
        init_db()
        _job("~a", "Applied job", "applied")
        _job("~b", "Found job", "found")
        result = runner.invoke(cli, ["pipeline", "view", "--stage", "applied"])
        assert "Applied job" in result.output
        assert "Found job" not in result.output

    def test_an_empty_stage_says_so_and_names_it(self, runner, isolated_config):
        init_db()
        _job("~a", "Found job", "found")
        result = runner.invoke(cli, ["pipeline", "view", "--stage", "won"])
        assert result.exit_code == 0
        assert 'at stage "won"' in result.output

    def test_a_job_with_no_score_shows_a_dash(self, runner, isolated_config):
        init_db()
        _job("~a", "Unscored", "found")
        assert "-" in runner.invoke(cli, ["pipeline", "view"]).output


class TestMove:
    def test_moving_reports_the_new_stage(self, runner, isolated_config):
        init_db()
        upsert_job(JobPosting(id="~a", title="Build an API"))
        result = runner.invoke(cli, ["pipeline", "move", "~a", "applied"])
        assert result.exit_code == 0
        assert "moved to" in result.output
        assert "applied" in result.output

    def test_notes_are_echoed(self, runner, isolated_config):
        init_db()
        upsert_job(JobPosting(id="~a", title="Build an API"))
        result = runner.invoke(
            cli, ["pipeline", "move", "~a", "applied", "--notes", "sent Monday"]
        )
        assert "sent Monday" in result.output

    def test_an_uncached_job_is_reported_not_a_traceback(self, runner, isolated_config):
        init_db()
        result = runner.invoke(cli, ["pipeline", "move", "~never", "won"])
        assert result.exit_code == 1
        assert "not in the local cache" in result.output

    def test_an_unknown_stage_is_refused_by_click(self, runner, isolated_config):
        init_db()
        result = runner.invoke(cli, ["pipeline", "move", "~a", "shortlisted"])
        assert result.exit_code != 0


class TestStats:
    def test_reports_counts_and_the_win_rate(self, runner, isolated_config):
        init_db()
        _job("~a", "Won job", "won")
        _job("~b", "Lost job", "lost")
        _job("~c", "New job", "found")
        result = runner.invoke(cli, ["pipeline", "stats"])
        assert result.exit_code == 0
        assert "Win Rate:" in result.output
        assert "50.0%" in result.output  # 1 won of 2 submitted; `found` excluded
        assert "Total" in result.output

    def test_top_categories_are_listed_when_present(self, runner, isolated_config):
        init_db()
        _job("~a", "Scraper", "applied", category="Data Science")
        result = runner.invoke(cli, ["pipeline", "stats"])
        assert "Top Categories" in result.output
        assert "Data Science" in result.output


class TestDigest:
    def test_lists_recent_transitions(self, runner, isolated_config):
        init_db()
        _job("~a", "Build an API", "applied")
        result = runner.invoke(cli, ["pipeline", "digest", "--days", "7"])
        assert result.exit_code == 0
        assert "Build an API" in result.output
        assert "applied" in result.output

    def test_nothing_recent_says_how_far_back_it_looked(self, runner, isolated_config):
        init_db()
        _job("~a", "Build an API", "applied")
        result = runner.invoke(cli, ["pipeline", "digest", "--days", "0"])
        assert result.exit_code == 0
        assert "last 0 day(s)" in result.output

    def test_an_empty_pipeline_has_no_activity(self, runner, isolated_config):
        init_db()
        result = runner.invoke(cli, ["pipeline", "digest"])
        assert result.exit_code == 0
        assert "No pipeline activity yet" in result.output
