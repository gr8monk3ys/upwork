"""Tests for the config command group and the Profile views it renders.

`commands/config.py` is the largest command module and was the least
covered: the whole `audit` command and both Profile serializers had no test
at all.
"""

import json

import pytest
from click.testing import CliRunner

from tests.fakes import FakeCompleter
from upwork_cli.ai.utils import AIError
from upwork_cli.cli import cli
from upwork_cli.config import Profile, save_profile

AUDIT_JSON = json.dumps(
    {
        "total_score": 72,
        "breakdown": [
            {"area": "Title", "score": 18, "feedback": "Strong."},
            {"area": "Overview", "score": 13, "feedback": "Thin."},
            {"area": "Portfolio", "score": 8, "feedback": "Add items."},
        ],
        "top_3_improvements": ["Add portfolio items.", "Expand overview."],
    }
)


@pytest.fixture
def runner():
    return CliRunner(env={"COLUMNS": "200"})


@pytest.fixture
def api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")


@pytest.fixture
def full_profile(isolated_config):
    save_profile(
        Profile(
            title="Senior Python Engineer",
            overview="Eight years building APIs.",
            skills=["Python", "FastAPI"],
            hourly_rate=75,
            experience_years=8,
            portfolio=[{"name": "Sizzle", "description": "A pipeline."}],
        )
    )


class TestProfileAuditSummary:
    """Distinct from `Profile.summary`: an audit grades completeness, so
    absent fields must be named rather than skipped."""

    def test_absent_fields_are_named_not_skipped(self):
        text = Profile().audit_summary()
        assert "Title: NOT SET" in text
        assert "Overview: NOT SET" in text
        assert "Skills: NONE" in text
        assert "Portfolio: NONE" in text
        assert "Hourly Rate: NOT SET" in text
        assert "Experience Years: NOT SET" in text

    def test_lengths_are_given_because_the_auditor_scores_on_them(self):
        text = Profile(title="Dev", overview="Hello").audit_summary()
        assert "Title (3 chars): Dev" in text
        assert "Overview (5 chars): Hello" in text

    def test_portfolio_items_are_listed_and_truncated(self):
        text = Profile(
            portfolio=[{"name": "Sizzle", "description": "x" * 200}]
        ).audit_summary()
        assert "Portfolio (1 items):" in text
        assert "- Sizzle: " + "x" * 100 in text
        assert "x" * 101 not in text

    def test_summary_omits_what_audit_summary_names(self):
        """The two views differ on purpose."""
        empty = Profile()
        assert empty.summary() == ""
        assert "NOT SET" in empty.audit_summary()


class TestConfigAudit:
    def test_scores_and_renders_the_breakdown(
        self, runner, full_profile, api_key, use_completer
    ):
        use_completer(FakeCompleter(AUDIT_JSON))
        result = runner.invoke(cli, ["config", "audit"])
        assert result.exit_code == 0, result.output
        assert "72/100" in result.output
        assert "Title" in result.output
        assert "Add portfolio items." in result.output

    def test_the_profile_reaches_the_auditor(
        self, runner, full_profile, api_key, use_completer
    ):
        fake = use_completer(FakeCompleter(AUDIT_JSON))
        runner.invoke(cli, ["config", "audit"])
        assert "Senior Python Engineer" in fake.prompt
        assert "chars" in fake.prompt

    def test_an_empty_profile_fails_before_calling_the_model(
        self, runner, isolated_config, api_key, use_completer
    ):
        fake = use_completer(FakeCompleter(AUDIT_JSON))
        save_profile(Profile())
        result = runner.invoke(cli, ["config", "audit"])
        assert result.exit_code == 1
        assert "Profile is empty" in result.output
        assert fake.calls == []

    def test_a_missing_api_key_fails_before_anything_else(
        self, runner, full_profile, monkeypatch
    ):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        result = runner.invoke(cli, ["config", "audit"])
        assert result.exit_code == 1
        assert "API key not configured" in result.output

    def test_a_model_failure_is_reported(
        self, runner, full_profile, api_key, use_completer
    ):
        use_completer(FakeCompleter(error=AIError("Anthropic call failed: down")))
        result = runner.invoke(cli, ["config", "audit"])
        assert result.exit_code == 1
        assert "Profile audit failed" in result.output


class TestConfigStatus:
    def test_status_reports_an_unconfigured_install(self, runner, isolated_config):
        result = runner.invoke(cli, ["config", "status"])
        assert result.exit_code == 0
        assert "Not authenticated" in result.output

    def test_status_names_where_a_secret_resolves_from(
        self, runner, isolated_config, monkeypatch
    ):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-from-env")
        result = runner.invoke(cli, ["config", "secrets"])
        assert result.exit_code == 0
        assert "ANTHROPIC_API_KEY" in result.output
        assert "sk-from-env" not in result.output  # never echo the value


class TestStyleGuideStorage:
    """`propose learn` wrote straight to `CONFIG_DIR / "style_guide.txt"`.

    On a fresh install -- no config directory yet -- that raised
    FileNotFoundError instead of saving. CI caught it; the local suite did
    not, because a passing earlier test had already made the directory.
    """

    def test_saving_creates_the_config_directory(self, isolated_config, monkeypatch):
        from upwork_cli import config as config_module

        assert not config_module.STYLE_GUIDE_FILE.exists()
        config_module.save_style_guide("## What works\nLead with results.")
        assert config_module.STYLE_GUIDE_FILE.exists()

    def test_round_trips(self, isolated_config):
        from upwork_cli.config import load_style_guide, save_style_guide

        save_style_guide("  ## What works  ")
        assert load_style_guide() == "## What works"

    def test_absent_reads_as_empty_not_an_error(self, isolated_config):
        from upwork_cli.config import load_style_guide

        assert load_style_guide() == ""

    def test_a_learnt_guide_reaches_the_next_draft(
        self, runner, isolated_config, api_key, use_completer
    ):
        from tests.fakes import FakeCompleter
        from upwork_cli.config import save_style_guide
        from upwork_cli.db import init_db, upsert_job
        from upwork_cli.models import JobPosting

        init_db()
        save_profile(Profile(title="Python dev"))
        upsert_job(JobPosting(id="~j", title="Build a scraper"))
        save_style_guide("Always open with a measurable result.")
        fake = use_completer(FakeCompleter("Drafted."))
        runner.invoke(cli, ["propose", "generate", "~j", "--no-research"])
        # The guide steers the drafter through its system prompt, not the user one.
        assert "Always open with a measurable result." in fake.calls[-1]["system"]
