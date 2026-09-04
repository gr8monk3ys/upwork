"""Tests for the earnings and contracts commands."""

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from tests.fakes import (
    FakeUpworkClient,
    earning_cells,
    earning_flat,
    earnings_payload,
    engagement_node,
    milestone_node,
)
from upwork_cli.cli import cli
from upwork_cli.client import NotAuthenticated
from upwork_cli.db import init_db
from upwork_cli.models import Milestone


@pytest.fixture
def runner():
    return CliRunner()


def _run(runner, args, client=None, **fake_kwargs):
    """Invoke the CLI with a fake client behind the single construction site."""
    client = client if client is not None else FakeUpworkClient(**fake_kwargs)
    with patch("upwork_cli.commands.earnings.get_client", return_value=client):
        return runner.invoke(cli, args)


# ---------------------------------------------------------------------------
# Helper tests
# ---------------------------------------------------------------------------


class TestMilestoneAmounts:
    """`_safe_float` was a second copy of `models._to_float`, used once.

    Its one caller was the milestone amount, which `Milestone.from_api`
    parses now; these keep the same coercions covered where they live.
    """

    def test_missing_amount_reads_as_zero(self):
        assert Milestone.from_api({"description": "Phase one"}).amount == 0.0

    def test_string_amount_is_parsed(self):
        assert Milestone.from_api({"amount": "42.5"}).amount == 42.5

    def test_unparseable_amount_reads_as_zero(self):
        assert Milestone.from_api({"amount": "not_a_number"}).amount == 0.0
        assert Milestone.from_api({"amount": [1, 2, 3]}).amount == 0.0

    def test_description_falls_back_through_title(self):
        assert Milestone.from_api({"title": "Phase two"}).description == "Phase two"
        assert Milestone.from_api({}).description == "Untitled"

    def test_status_falls_back_through_state(self):
        assert Milestone.from_api({"state": "funded"}).status == "funded"


class TestSummaryCommand:
    def test_not_authenticated(self, runner, isolated_config):
        with patch(
            "upwork_cli.commands.earnings.get_client",
            side_effect=NotAuthenticated("nope"),
        ):
            result = runner.invoke(cli, ["earnings", "summary"])
        assert result.exit_code == 1
        assert "Not authenticated" in result.output

    def test_renders_totals(self, runner, isolated_config):
        result = _run(
            runner,
            ["earnings", "summary"],
            earnings=earnings_payload(
                earning_cells(date="2026-09-01", amount="1200.00"),
                earning_cells(date="2020-01-01", amount="300.00"),
            ),
        )
        assert result.exit_code == 0
        assert "$1,500.00" in result.output

    def test_empty_data(self, runner, isolated_config):
        result = _run(runner, ["earnings", "summary"], earnings=earnings_payload())
        assert result.exit_code == 0
        assert "No earnings data available yet" in result.output

    def test_api_failure(self, runner, isolated_config):
        result = _run(
            runner, ["earnings", "summary"], earnings=RuntimeError("upstream")
        )
        assert result.exit_code == 1
        assert "fetch earnings" in result.output


class TestReportCommand:
    def test_table_format(self, runner, isolated_config):
        result = _run(
            runner,
            ["earnings", "report"],
            earnings=earnings_payload(
                earning_cells(client="Acme Corp", amount="1200.00")
            ),
        )
        assert result.exit_code == 0
        assert "Acme Corp" in result.output

    def test_uses_the_reports_own_column_labels(self, runner, isolated_config):
        result = _run(
            runner,
            ["earnings", "report"],
            earnings=earnings_payload(
                earning_cells(), cols=["When", "Who", "What", "Amt", "Kind"]
            ),
        )
        assert "When" in result.output

    def test_csv_format(self, runner, isolated_config):
        result = _run(
            runner,
            ["earnings", "report", "--format", "csv"],
            earnings=earnings_payload(
                earning_cells(date="2026-09-01", client="Acme Corp")
            ),
        )
        assert result.exit_code == 0
        assert "2026-09-01,Acme Corp" in result.output

    def test_date_filtering_reaches_the_client(self, runner, isolated_config):
        client = FakeUpworkClient(earnings=earnings_payload(earning_cells()))
        _run(
            runner,
            ["earnings", "report", "--from", "2026-01-01", "--to", "2026-06-30"],
            client=client,
        )
        assert client.earnings_params == [
            {"tq": "date >= '2026-01-01' AND date <= '2026-06-30'"}
        ]

    def test_empty_report(self, runner, isolated_config):
        result = _run(runner, ["earnings", "report"], earnings=earnings_payload())
        assert result.exit_code == 0
        assert "No earnings found" in result.output

    def test_flat_rows_render_too(self, runner, isolated_config):
        result = _run(
            runner,
            ["earnings", "report"],
            earnings={"rows": [earning_flat(client="Beta LLC")]},
        )
        assert "Beta LLC" in result.output


class TestExportCommand:
    def test_writes_a_csv(self, runner, isolated_config, tmp_path):
        out = tmp_path / "earnings.csv"
        result = _run(
            runner,
            ["earnings", "export", "--output", str(out)],
            earnings=earnings_payload(
                earning_cells(date="2026-09-01", client="Acme Corp")
            ),
        )
        assert result.exit_code == 0
        text = out.read_text()
        assert text.splitlines()[0] == "Date,Client,Contract,Amount,Type"
        assert "2026-09-01,Acme Corp" in text

    def test_nothing_to_export(self, runner, isolated_config, tmp_path):
        out = tmp_path / "earnings.csv"
        result = _run(
            runner,
            ["earnings", "export", "--output", str(out)],
            earnings=earnings_payload(),
        )
        assert result.exit_code == 0
        assert "No earnings data to export" in result.output
        assert not out.exists()


class TestContractsCommands:
    """Driven through FakeUpworkClient like every other slice.

    These used to build a MagicMock, because the fake had no
    `get_engagements` / `get_engagement` / `submit_work` -- the contracts
    group was the one part of the Upwork seam it did not cover.
    """

    def test_list_renders_contracts(self, runner, isolated_config):
        init_db()
        result = _run(
            runner,
            ["contracts", "list"],
            engagements={
                "engagements": {
                    "engagement": [engagement_node(title="API Development")]
                }
            },
        )
        assert result.exit_code == 0
        assert "API Development" in result.output
        assert "Acme Inc" in result.output

    def test_list_accepts_a_bare_dict_for_one_contract(self, runner, isolated_config):
        """Upwork returns one engagement unwrapped rather than in a list."""
        init_db()
        result = _run(
            runner,
            ["contracts", "list"],
            engagements={"engagement": engagement_node(title="Solo Contract")},
        )
        assert result.exit_code == 0
        assert "Solo Contract" in result.output

    def test_list_empty(self, runner, isolated_config):
        init_db()
        result = _run(runner, ["contracts", "list"], engagements={})
        assert result.exit_code == 0
        assert "No active contracts" in result.output

    def test_list_api_failure_exits_nonzero(self, runner, isolated_config):
        init_db()
        result = _run(
            runner, ["contracts", "list"], engagements=RuntimeError("upstream 503")
        )
        assert result.exit_code == 1
        assert "Failed to fetch contracts" in result.output

    def test_detail_displays_info(self, runner, isolated_config):
        init_db()
        result = _run(
            runner,
            ["contracts", "detail", "eng-2"],
            engagement={"engagement": engagement_node(title="Backend Work")},
        )
        assert result.exit_code == 0
        assert "Backend Work" in result.output

    def test_detail_lists_milestones(self, runner, isolated_config):
        init_db()
        result = _run(
            runner,
            ["contracts", "detail", "eng-2"],
            engagement={
                "engagement": engagement_node(
                    milestones=[milestone_node("Phase one", amount=1500.0)]
                )
            },
        )
        assert result.exit_code == 0
        assert "Phase one" in result.output
        assert "1,500.00" in result.output

    def test_detail_handles_a_payload_with_no_envelope(self, runner, isolated_config):
        init_db()
        result = _run(
            runner,
            ["contracts", "detail", "eng-2"],
            engagement=engagement_node(title="Unwrapped"),
        )
        assert result.exit_code == 0
        assert "Unwrapped" in result.output

    def test_submit_confirm(self, runner, isolated_config):
        init_db()
        client = FakeUpworkClient(engagement={"engagement": engagement_node()})
        with patch("upwork_cli.commands.earnings.get_client", return_value=client):
            result = runner.invoke(
                cli,
                ["contracts", "submit", "eng-1", "--message", "done"],
                input="y\n",
            )
        assert result.exit_code == 0, result.output
        assert "submitted successfully" in result.output
        assert client.submitted == [
            {"engagement__reference": "eng-1", "comments": "done"}
        ]

    def test_submit_cancel_sends_nothing(self, runner, isolated_config):
        init_db()
        client = FakeUpworkClient(engagement={"engagement": engagement_node()})
        with patch("upwork_cli.commands.earnings.get_client", return_value=client):
            result = runner.invoke(cli, ["contracts", "submit", "eng-1"], input="n\n")
        assert result.exit_code == 0
        assert "cancelled" in result.output
        assert client.submitted == []

    def test_not_authenticated(self, runner, isolated_config):
        init_db()
        with patch(
            "upwork_cli.commands.earnings.get_client",
            side_effect=NotAuthenticated("nope"),
        ):
            result = runner.invoke(cli, ["contracts", "list"])
        assert result.exit_code != 0
        assert "Not authenticated" in result.output
