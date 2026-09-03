"""Tests for the earnings and contracts commands."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from tests.fakes import (
    FakeUpworkClient,
    earning_cells,
    earning_flat,
    earnings_payload,
)
from upwork_cli.cli import cli
from upwork_cli.client import NotAuthenticated
from upwork_cli.db import init_db


@pytest.fixture
def runner():
    return CliRunner()


def _run(runner, args, client=None, **fake_kwargs):
    """Invoke the CLI with a fake client behind the single construction site."""
    client = client if client is not None else FakeUpworkClient(**fake_kwargs)
    with patch("upwork_cli.commands.earnings.get_client", return_value=client):
        return runner.invoke(cli, args)


def _make_mock_client(authenticated=True):
    """Create a mock UpworkClient with basic stubs."""
    client = MagicMock()
    client.is_authenticated = authenticated
    client.get_user_info.return_value = {"info": {"ref": "~freelancer123"}}
    return client


# ---------------------------------------------------------------------------
# Helper tests
# ---------------------------------------------------------------------------


class TestSafeFloat:
    def test_none_returns_default(self):
        from upwork_cli.commands.earnings import _safe_float

        assert _safe_float(None) == 0.0

    def test_valid_number(self):
        from upwork_cli.commands.earnings import _safe_float

        assert _safe_float("42.5") == 42.5

    def test_integer_input(self):
        from upwork_cli.commands.earnings import _safe_float

        assert _safe_float(10) == 10.0

    def test_value_error(self):
        from upwork_cli.commands.earnings import _safe_float

        assert _safe_float("not_a_number") == 0.0

    def test_type_error(self):
        from upwork_cli.commands.earnings import _safe_float

        assert _safe_float([1, 2, 3]) == 0.0

    def test_custom_default(self):
        from upwork_cli.commands.earnings import _safe_float

        assert _safe_float(None, default=-1.0) == -1.0


class TestFormatCurrency:
    def test_basic_amount(self):
        from upwork_cli.commands.earnings import _format_currency

        assert _format_currency(1234.56) == "$1,234.56"

    def test_zero(self):
        from upwork_cli.commands.earnings import _format_currency

        assert _format_currency(0) == "$0.00"

    def test_large_amount(self):
        from upwork_cli.commands.earnings import _format_currency

        result = _format_currency(1000000.0)
        assert "$1,000,000.00" == result


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
    @patch("upwork_cli.commands.earnings.get_client")
    def test_list_happy_path(self, MockClient, runner, isolated_config):
        init_db()
        client = _make_mock_client()
        client.get_engagements.return_value = {
            "engagements": {
                "engagement": [
                    {
                        "job": {"title": "API Development"},
                        "buyer": {"company_name": "Acme Corp"},
                        "status": "active",
                        "hourly_charge_rate": {"amount": 75.00},
                        "hours_per_week": 120.5,
                        "total_charge": {"amount": 9037.50},
                        "reference": "~eng001",
                        "created_time": "2025-01-01",
                    }
                ]
            }
        }
        MockClient.return_value = client
        result = runner.invoke(cli, ["contracts", "list"])
        assert result.exit_code == 0
        assert "Contracts" in result.output

    @patch("upwork_cli.commands.earnings.get_client")
    def test_list_empty(self, MockClient, runner, isolated_config):
        init_db()
        client = _make_mock_client()
        client.get_engagements.return_value = {}
        MockClient.return_value = client
        result = runner.invoke(cli, ["contracts", "list"])
        assert result.exit_code == 0
        assert "No active contracts" in result.output

    @patch("upwork_cli.commands.earnings.get_client")
    def test_detail_displays_info(self, MockClient, runner, isolated_config):
        init_db()
        client = _make_mock_client()
        client.get_engagement.return_value = {
            "engagement": {
                "job": {"title": "Backend Work"},
                "buyer": {"company_name": "ClientCo"},
                "status": "active",
                "hourly_charge_rate": {"amount": 100.00},
                "hours_per_week": 50.0,
                "total_charge": {"amount": 5000.00},
                "reference": "~eng002",
                "created_time": "2025-02-01",
            }
        }
        MockClient.return_value = client
        result = runner.invoke(cli, ["contracts", "detail", "~eng002"])
        assert result.exit_code == 0
        assert "Contract" in result.output

    @patch("upwork_cli.commands.earnings.get_client")
    def test_detail_with_status_colors(self, MockClient, runner, isolated_config):
        init_db()
        client = _make_mock_client()
        client.get_engagement.return_value = {
            "engagement": {
                "job": {"title": "Old Project"},
                "buyer": {"company_name": "OldClient"},
                "status": "ended",
                "reference": "~eng003",
                "created_time": "2024-06-01",
            }
        }
        MockClient.return_value = client
        result = runner.invoke(cli, ["contracts", "detail", "~eng003"])
        assert result.exit_code == 0

    @patch("upwork_cli.commands.earnings.get_client")
    def test_submit_confirm(self, MockClient, runner, isolated_config):
        init_db()
        client = _make_mock_client()
        client.get_engagement.return_value = {
            "engagement": {
                "job": {"title": "Milestone Project"},
                "buyer": {"company_name": "MilestoneCo"},
                "status": "active",
                "reference": "~eng004",
                "created_time": "2025-01-01",
            }
        }
        client.submit_work.return_value = {}
        MockClient.return_value = client
        result = runner.invoke(cli, ["contracts", "submit", "~eng004"], input="y\n")
        assert result.exit_code == 0
        assert "submitted successfully" in result.output

    @patch("upwork_cli.commands.earnings.get_client")
    def test_submit_cancel(self, MockClient, runner, isolated_config):
        init_db()
        client = _make_mock_client()
        client.get_engagement.return_value = {
            "engagement": {
                "job": {"title": "Milestone Project"},
                "buyer": {"company_name": "MilestoneCo"},
                "status": "active",
                "reference": "~eng005",
                "created_time": "2025-01-01",
            }
        }
        MockClient.return_value = client
        result = runner.invoke(cli, ["contracts", "submit", "~eng005"], input="n\n")
        assert result.exit_code == 0
        assert "cancelled" in result.output

    @patch("upwork_cli.commands.earnings.get_client")
    def test_not_authenticated(self, MockClient, runner, isolated_config):
        init_db()
        MockClient.side_effect = NotAuthenticated("not authenticated")
        result = runner.invoke(cli, ["contracts", "list"])
        assert result.exit_code != 0
        assert "Not authenticated" in result.output
