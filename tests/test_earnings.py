"""Tests for the earnings and contracts commands."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from upwork_cli.cli import cli
from upwork_cli.client import NotAuthenticated
from upwork_cli.db import init_db


@pytest.fixture
def runner():
    return CliRunner()


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


class TestGetFreelancerRef:
    @patch("upwork_cli.commands.earnings.get_client")
    def test_happy_path(self, MockClient, runner, isolated_config):
        from upwork_cli.commands.earnings import _get_freelancer_ref

        client = _make_mock_client()
        ref = _get_freelancer_ref(client)
        assert ref == "~freelancer123"

    @patch("upwork_cli.commands.earnings.get_client")
    def test_fallback_ref(self, MockClient, runner, isolated_config):
        from upwork_cli.commands.earnings import _get_freelancer_ref

        client = _make_mock_client()
        client.get_user_info.return_value = {"id": "alt-ref-456"}
        ref = _get_freelancer_ref(client)
        assert ref == "alt-ref-456"

    @patch("upwork_cli.commands.earnings.get_client")
    def test_error_raises_system_exit(self, MockClient, runner, isolated_config):
        from upwork_cli.commands.earnings import _get_freelancer_ref

        client = _make_mock_client()
        client.get_user_info.side_effect = Exception("API down")
        with pytest.raises(SystemExit):
            _get_freelancer_ref(client)


# ---------------------------------------------------------------------------
# Earnings summary command
# ---------------------------------------------------------------------------


class TestSummaryCommand:
    @patch("upwork_cli.commands.earnings.get_client")
    def test_not_authenticated(self, MockClient, runner, isolated_config):
        init_db()
        MockClient.side_effect = NotAuthenticated("not authenticated")
        result = runner.invoke(cli, ["earnings", "summary"])
        assert result.exit_code != 0
        assert "Not authenticated" in result.output

    @patch("upwork_cli.commands.earnings.get_client")
    def test_happy_path_with_data(self, MockClient, runner, isolated_config):
        init_db()
        client = _make_mock_client()
        client.get_earnings.return_value = {
            "table": {
                "rows": [
                    {"amount": 500.0, "date": "2025-01-10"},
                    {"amount": 1200.0, "date": "2025-01-15"},
                ]
            }
        }
        MockClient.return_value = client
        result = runner.invoke(cli, ["earnings", "summary"])
        assert result.exit_code == 0
        assert "Earnings Summary" in result.output
        assert "Total Earned" in result.output

    @patch("upwork_cli.commands.earnings.get_client")
    def test_empty_data(self, MockClient, runner, isolated_config):
        init_db()
        client = _make_mock_client()
        client.get_earnings.return_value = {"table": {"rows": []}}
        MockClient.return_value = client
        result = runner.invoke(cli, ["earnings", "summary"])
        assert result.exit_code == 0
        assert "No earnings data" in result.output

    @patch("upwork_cli.commands.earnings.get_client")
    def test_api_failure(self, MockClient, runner, isolated_config):
        init_db()
        client = _make_mock_client()
        client.get_earnings.side_effect = Exception("timeout")
        MockClient.return_value = client
        result = runner.invoke(cli, ["earnings", "summary"])
        assert result.exit_code != 0
        assert "Failed to fetch earnings" in result.output


# ---------------------------------------------------------------------------
# Earnings report command
# ---------------------------------------------------------------------------


class TestReportCommand:
    @patch("upwork_cli.commands.earnings.get_client")
    def test_table_format(self, MockClient, runner, isolated_config):
        init_db()
        client = _make_mock_client()
        client.get_earnings.return_value = {
            "table": {
                "cols": [
                    {"label": "Date"},
                    {"label": "Client"},
                    {"label": "Contract"},
                    {"label": "Amount"},
                    {"label": "Type"},
                ],
                "rows": [
                    {
                        "c": [
                            {"v": "2025-01-10"},
                            {"v": "Acme Corp"},
                            {"v": "API Dev"},
                            {"v": "500.00"},
                            {"v": "Hourly"},
                        ]
                    }
                ],
            }
        }
        MockClient.return_value = client
        result = runner.invoke(cli, ["earnings", "report"])
        assert result.exit_code == 0
        assert "Earnings Report" in result.output

    @patch("upwork_cli.commands.earnings.get_client")
    def test_csv_format(self, MockClient, runner, isolated_config):
        init_db()
        client = _make_mock_client()
        client.get_earnings.return_value = {
            "rows": [
                {
                    "date": "2025-01-10",
                    "client": "Acme",
                    "contract": "Dev",
                    "amount": "500",
                    "type": "Hourly",
                }
            ]
        }
        MockClient.return_value = client
        result = runner.invoke(cli, ["earnings", "report", "--format", "csv"])
        assert result.exit_code == 0
        assert "Date" in result.output
        assert "500" in result.output

    @patch("upwork_cli.commands.earnings.get_client")
    def test_date_filtering(self, MockClient, runner, isolated_config):
        init_db()
        client = _make_mock_client()
        client.get_earnings.return_value = {"rows": []}
        MockClient.return_value = client
        result = runner.invoke(
            cli, ["earnings", "report", "--from", "2025-01-01", "--to", "2025-01-31"]
        )
        assert result.exit_code == 0
        assert "No earnings found" in result.output

    @patch("upwork_cli.commands.earnings.get_client")
    def test_empty_report(self, MockClient, runner, isolated_config):
        init_db()
        client = _make_mock_client()
        client.get_earnings.return_value = {"table": {"rows": []}}
        MockClient.return_value = client
        result = runner.invoke(cli, ["earnings", "report"])
        assert result.exit_code == 0
        assert "No earnings found" in result.output


# ---------------------------------------------------------------------------
# Contracts commands
# ---------------------------------------------------------------------------


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
