"""Tests for the propose command group (API-free drafting, pipeline stages)."""

from unittest.mock import patch

import click
import pytest
from click.testing import CliRunner

from upwork_cli.cli import cli
from upwork_cli.commands.propose import _job_from_description, _open_in_editor
from upwork_cli.db import get_connection, get_pipeline_jobs, init_db


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")


class TestJobFromDescription:
    def test_builds_job_and_caches(self, isolated_config):
        init_db()
        job = _job_from_description(
            "# Senior Python Dev\n\nBuild an API.", title=None, job_id=None
        )
        assert job.title == "Senior Python Dev"
        assert job.id.startswith("manual-")
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job.id,)).fetchone()
        assert row is not None
        assert "Build an API." in row["description"]

    def test_explicit_title_and_id(self, isolated_config):
        init_db()
        job = _job_from_description("text body", title="My Job", job_id="custom-1")
        assert job.title == "My Job"
        assert job.id == "custom-1"

    def test_empty_text_raises(self, isolated_config):
        init_db()
        with pytest.raises(click.UsageError, match="empty"):
            _job_from_description("   \n  ", title=None, job_id=None)

    def test_same_text_same_id(self, isolated_config):
        init_db()
        a = _job_from_description("identical posting", title=None, job_id=None)
        b = _job_from_description("identical posting", title=None, job_id=None)
        assert a.id == b.id


class TestGenerateFromFile:
    def test_drafts_without_api_and_marks_drafted(
        self, runner, isolated_config, api_key, tmp_path
    ):
        job_file = tmp_path / "job.md"
        job_file.write_text("# React Dashboard\n\nNeed a dashboard built fast.")

        with patch(
            "upwork_cli.commands.propose.draft_proposal",
            return_value="Here is the draft.",
        ) as mock_draft:
            result = runner.invoke(
                cli, ["propose", "generate", "--from-file", str(job_file)]
            )

        assert result.exit_code == 0, result.output
        mock_draft.assert_called_once()
        assert "React Dashboard" in mock_draft.call_args.kwargs["job_summary"]

        # A draft is NOT an application: stage must be "drafted", not "applied".
        drafted = get_pipeline_jobs(stage="drafted")
        assert len(drafted) == 1
        assert get_pipeline_jobs(stage="applied") == []

        with get_connection() as conn:
            row = conn.execute("SELECT * FROM proposals").fetchone()
        assert row["content"] == "Here is the draft."

    def test_requires_job_id_or_file(self, runner, isolated_config, api_key):
        result = runner.invoke(cli, ["propose", "generate"])
        assert result.exit_code != 0
        assert "JOB_ID or --from-file" in result.output

    def test_missing_api_key_fails_cleanly(self, runner, isolated_config, tmp_path):
        job_file = tmp_path / "job.md"
        job_file.write_text("A job")
        result = runner.invoke(
            cli, ["propose", "generate", "--from-file", str(job_file)]
        )
        assert result.exit_code == 1
        assert "Anthropic API key not configured" in result.output


class TestRefineById:
    def test_refines_specific_proposal(self, runner, isolated_config, api_key):
        from upwork_cli.db import save_proposal

        init_db()
        first = save_proposal("job-1", "First", "First draft", "professional")
        save_proposal("job-2", "Second", "Second draft", "professional")

        with patch(
            "upwork_cli.commands.propose.refine_proposal",
            return_value="Refined first.",
        ) as mock_refine:
            result = runner.invoke(
                cli,
                ["propose", "refine", str(first), "--feedback", "shorter"],
            )

        assert result.exit_code == 0, result.output
        assert mock_refine.call_args.kwargs["current_draft"] == "First draft"

    def test_unknown_id_fails(self, runner, isolated_config, api_key):
        init_db()
        result = runner.invoke(
            cli, ["propose", "refine", "999", "--feedback", "shorter"]
        )
        assert result.exit_code == 1
        assert "not found" in result.output


class TestOpenInEditor:
    def test_editor_with_arguments(self, monkeypatch):
        monkeypatch.setenv("EDITOR", "code -w")
        captured = {}

        def fake_call(cmd):
            captured["cmd"] = cmd
            return 0

        with patch("upwork_cli.commands.propose.subprocess.call", fake_call):
            _open_in_editor("draft text")

        assert captured["cmd"][:2] == ["code", "-w"]
        assert captured["cmd"][2].endswith(".md")
