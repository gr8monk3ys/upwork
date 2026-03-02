"""CLI smoke tests using Click's CliRunner.

These verify that commands load, parse arguments, and produce reasonable
output without hitting real APIs.
"""

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from upwork_cli.cli import cli
from upwork_cli.db import init_db


@pytest.fixture
def runner():
    return CliRunner()


class TestConfigCommands:
    def test_status_unauthenticated(self, runner, isolated_config):
        init_db()
        result = runner.invoke(cli, ["config", "status"])
        assert result.exit_code == 0
        assert "Not authenticated" in result.output

    def test_profile_from_markdown_file(self, runner, isolated_config, tmp_path):
        init_db()
        md_file = tmp_path / "profile.md"
        md_file.write_text(
            "## Professional Title\nTest Dev\n\n"
            "## Professional Overview\nI build things.\n\n"
            "## Skills to Add\n- Python\n- Go\n"
        )
        result = runner.invoke(cli, ["config", "profile", "--file", str(md_file)])
        assert result.exit_code == 0
        assert "Profile saved" in result.output

    def test_profile_unsupported_format(self, runner, isolated_config, tmp_path):
        init_db()
        txt_file = tmp_path / "profile.txt"
        txt_file.write_text("just text")
        result = runner.invoke(cli, ["config", "profile", "--file", str(txt_file)])
        assert result.exit_code != 0
        assert "Unsupported file type" in result.output

    def test_reset_aborted(self, runner, isolated_config):
        init_db()
        result = runner.invoke(cli, ["config", "reset"], input="n\n")
        assert "Aborted" in result.output


class TestJobsCommands:
    def test_saved_empty(self, runner, isolated_config):
        init_db()
        result = runner.invoke(cli, ["jobs", "saved"])
        assert result.exit_code == 0
        assert "No bookmarks" in result.output


class TestProposeCommands:
    def test_history_empty(self, runner, isolated_config):
        init_db()
        result = runner.invoke(cli, ["propose", "history"])
        assert result.exit_code == 0
        assert "No proposals" in result.output

    def test_show_not_found(self, runner, isolated_config):
        init_db()
        result = runner.invoke(cli, ["propose", "show", "999"])
        assert result.exit_code != 0
        assert "not found" in result.output

    def test_generate_no_api_key(self, runner, isolated_config):
        init_db()
        result = runner.invoke(cli, ["propose", "generate", "~01abc"])
        assert result.exit_code != 0
        assert "API key" in result.output

    def test_refine_no_api_key(self, runner, isolated_config):
        init_db()
        result = runner.invoke(cli, ["propose", "refine"])
        assert result.exit_code != 0
        assert "API key" in result.output

    def test_mark_not_found(self, runner, isolated_config):
        init_db()
        result = runner.invoke(cli, ["propose", "mark", "999", "won"])
        assert result.exit_code != 0
        assert "not found" in result.output

    def test_mark_lost_not_found(self, runner, isolated_config):
        init_db()
        result = runner.invoke(cli, ["propose", "mark", "999", "lost"])
        assert result.exit_code != 0
        assert "not found" in result.output

    def test_learn_no_api_key(self, runner, isolated_config):
        init_db()
        result = runner.invoke(cli, ["propose", "learn"])
        assert result.exit_code != 0
        assert "API key" in result.output

    def test_prep_no_api_key(self, runner, isolated_config):
        init_db()
        result = runner.invoke(cli, ["propose", "prep", "~01abc"])
        assert result.exit_code != 0
        assert "API key" in result.output

    def test_prep_job_not_in_db(self, runner, isolated_config, mock_keyring):
        """prep with API key set but job not cached returns error."""
        init_db()
        mock_keyring["upwork-cli:anthropic_api_key"] = "sk-ant-test"
        result = runner.invoke(cli, ["propose", "prep", "~01nonexistent"])
        assert result.exit_code != 0
        assert "not found" in result.output


class TestPipelineCommands:
    def test_view_empty(self, runner, isolated_config):
        init_db()
        result = runner.invoke(cli, ["pipeline", "view"])
        assert result.exit_code == 0

    def test_digest_empty(self, runner, isolated_config):
        init_db()
        result = runner.invoke(cli, ["pipeline", "digest"])
        assert result.exit_code == 0
        assert "No pipeline activity" in result.output

    def test_stats_empty(self, runner, isolated_config):
        init_db()
        result = runner.invoke(cli, ["pipeline", "stats"])
        assert result.exit_code == 0
