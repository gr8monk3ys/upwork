"""CLI smoke tests using Click's CliRunner.

These verify that commands load, parse arguments, and produce reasonable
output without hitting real APIs.
"""

from unittest.mock import MagicMock, patch

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

    def test_reset_deletes_db_and_style_guide(self, runner, isolated_config):
        init_db()
        style_guide = isolated_config / "style_guide.txt"
        style_guide.write_text("Learned patterns")

        result = runner.invoke(cli, ["config", "reset"], input="y\n")

        assert result.exit_code == 0
        assert not (isolated_config / "upwork.db").exists()
        assert not style_guide.exists()

    def test_secret_status_empty(self, runner, isolated_config):
        init_db()
        result = runner.invoke(cli, ["config", "secrets", "status"])
        assert result.exit_code == 0
        assert "Secret Status" in result.output
        assert "Not set" in result.output

    def test_secret_clear_removes_keyring_value(
        self, runner, isolated_config, mock_keyring
    ):
        init_db()
        mock_keyring["upwork-cli:anthropic_api_key"] = "sk-ant-test"
        result = runner.invoke(
            cli, ["config", "secrets", "clear", "anthropic-api-key", "--yes"]
        )
        assert result.exit_code == 0
        assert "Cleared Anthropic API Key" in result.output
        assert "upwork-cli:anthropic_api_key" not in mock_keyring

    @patch("upwork_cli.commands.config.webbrowser.open")
    @patch("upwork_cli.commands.config.UpworkClient")
    def test_setup_keeps_existing_secret_on_blank_input(
        self, MockClient, mock_browser, runner, isolated_config, mock_keyring
    ):
        init_db()
        mock_keyring["upwork-cli:client_secret"] = "existing-secret"

        client = MockClient.return_value
        client.get_authorization_url.return_value = "https://example.com/auth"
        client.complete_auth.return_value = MagicMock()
        client.get_user_info.return_value = {
            "user": {"first_name": "Test", "last_name": "User"}
        }

        result = runner.invoke(
            cli,
            ["config", "setup"],
            input=(
                "client-id-123\n\n\n\n\nhttps://localhost:8080/callback?code=test\n"
            ),
        )

        assert result.exit_code == 0
        assert mock_keyring["upwork-cli:client_secret"] == "existing-secret"

    @patch("upwork_cli.commands.config.webbrowser.open")
    @patch("upwork_cli.commands.config.UpworkClient")
    def test_setup_allows_clearing_a_single_secret(
        self, MockClient, mock_browser, runner, isolated_config, mock_keyring
    ):
        init_db()
        mock_keyring["upwork-cli:anthropic_api_key"] = "sk-ant-test"

        client = MockClient.return_value
        client.get_authorization_url.return_value = "https://example.com/auth"
        client.complete_auth.return_value = MagicMock()
        client.get_user_info.return_value = {
            "user": {"first_name": "Test", "last_name": "User"}
        }

        result = runner.invoke(
            cli,
            ["config", "setup"],
            input=(
                "client-id-123\n"
                "\n"
                "\n"
                "clear\n"
                "\n"
                "https://localhost:8080/callback?code=test\n"
            ),
        )

        assert result.exit_code == 0
        assert "upwork-cli:anthropic_api_key" not in mock_keyring


class TestJobsCommands:
    def test_saved_empty(self, runner, isolated_config):
        init_db()
        result = runner.invoke(cli, ["jobs", "saved"])
        assert result.exit_code == 0
        assert "No bookmarks" in result.output

    def test_saved_searches_list_empty(self, runner, isolated_config):
        init_db()
        result = runner.invoke(cli, ["jobs", "searches", "list"])
        assert result.exit_code == 0
        assert "No saved search terms" in result.output

    def test_saved_searches_add_and_list(self, runner, isolated_config):
        init_db()
        add_result = runner.invoke(cli, ["jobs", "searches", "add", "python developer"])
        list_result = runner.invoke(cli, ["jobs", "searches", "list"])
        assert add_result.exit_code == 0
        assert "Added saved search" in add_result.output
        assert "python developer" in list_result.output

    def test_saved_searches_remove(self, runner, isolated_config):
        init_db()
        runner.invoke(cli, ["jobs", "searches", "add", "python developer"])
        result = runner.invoke(cli, ["jobs", "searches", "remove", "python developer"])
        assert result.exit_code == 0
        assert "Removed saved search" in result.output

    def test_saved_searches_run_requires_terms(self, runner, isolated_config):
        init_db()
        result = runner.invoke(cli, ["jobs", "searches", "run"])
        assert result.exit_code != 0
        assert "No saved search terms configured" in result.output

    def test_saved_searches_run_requires_auth(self, runner, isolated_config):
        init_db()
        runner.invoke(cli, ["jobs", "searches", "add", "python developer"])
        result = runner.invoke(cli, ["jobs", "searches", "run"])
        assert result.exit_code != 0
        assert "Not authenticated" in result.output


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
        assert "No jobs in the pipeline" in result.output

    def test_digest_empty(self, runner, isolated_config):
        init_db()
        result = runner.invoke(cli, ["pipeline", "digest"])
        assert result.exit_code == 0
        assert "No pipeline activity" in result.output

    def test_stats_empty(self, runner, isolated_config):
        init_db()
        result = runner.invoke(cli, ["pipeline", "stats"])
        assert result.exit_code == 0
        assert "No jobs in the pipeline yet" in result.output
