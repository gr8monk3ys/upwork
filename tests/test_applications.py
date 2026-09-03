"""Tests for GraphQL-backed applications and offers commands."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from upwork_cli.cli import cli
from upwork_cli.client import NotAuthenticated
from upwork_cli.db import init_db


@pytest.fixture
def runner():
    return CliRunner()


def _make_mock_client(authenticated: bool = True) -> MagicMock:
    """Create a mock Upwork client with GraphQL-shaped responses."""
    client = MagicMock()
    client.is_authenticated = authenticated
    client.get_applications.return_value = {
        "edges": [
            {
                "node": {
                    "id": "app-001",
                    "status": {"status": "Accepted"},
                    "auditDetails": {
                        "createdDateTime": "2026-03-01T08:00:00Z",
                        "modifiedDateTime": "2026-03-02T10:15:00Z",
                    },
                    "marketplaceJobPosting": {
                        "id": "~job001",
                        "title": "Python API Cleanup",
                        "createdDateTime": "2026-02-28T20:00:00Z",
                    },
                }
            }
        ]
    }
    client.get_application.return_value = {
        "id": "app-001",
        "status": {"status": "Accepted"},
        "proposalCoverLetter": "I can clean this API safely and quickly.",
        "auditDetails": {
            "createdDateTime": "2026-03-01T08:00:00Z",
            "modifiedDateTime": "2026-03-02T10:15:00Z",
        },
        "marketplaceJobPosting": {
            "id": "~job001",
            "title": "Python API Cleanup",
            "description": "Refactor an aging FastAPI service.",
            "engagement": "Hourly: 10+ hrs/week",
            "durationLabel": "1 to 3 months",
            "amount": {"amount": 75, "currencyCode": "USD"},
            "client": {
                "totalHires": 12,
                "totalSpent": {"amount": 25000, "currencyCode": "USD"},
                "verificationStatus": "VERIFIED",
                "location": {"country": "United States"},
            },
        },
    }
    client.get_offers_for_application.return_value = [
        {
            "id": "offer-001",
            "title": "Backend Retainer",
            "state": "PENDING_VENDOR_ACCEPTANCE",
            "client": {"name": "Acme Corp"},
            "offerTerms": {
                "hourlyTerms": {
                    "rate": {"amount": 85, "currencyCode": "USD"},
                    "weeklyHoursLimit": 20,
                }
            },
        }
    ]
    client.get_offers.return_value = {
        "edges": [
            {
                "node": {
                    "id": "wrapped-offer-001",
                    "title": "Backend Retainer",
                    "state": "Pending",
                    "type": "Hourly",
                    "lastUpdatedDateTime": "2026-03-05T18:30:00Z",
                    "company": {"name": "Acme Corp"},
                    "offer": {
                        "id": "offer-001",
                        "state": "PENDING_VENDOR_ACCEPTANCE",
                        "vendorProposal": {"id": "app-001"},
                    },
                }
            }
        ]
    }
    client.get_offer.return_value = {
        "id": "offer-001",
        "title": "Backend Retainer",
        "description": "Join the team for platform stabilization.",
        "type": "Hourly",
        "state": "PENDING_VENDOR_ACCEPTANCE",
        "closeJobPostingOnAccept": True,
        "messageToContractor": "We want to move quickly.",
        "client": {"name": "Acme Corp"},
        "job": {"id": "~job001", "title": "Python API Cleanup"},
        "vendorProposal": {
            "id": "app-001",
            "status": {"status": "Accepted"},
        },
        "offerTerms": {
            "expectedStartDate": "2026-03-10",
            "expectedEndDate": "2026-06-10",
            "hourlyTerms": {
                "rate": {"amount": 85, "currencyCode": "USD"},
                "weeklyHoursLimit": 20,
                "manualTimeAllowed": True,
            },
        },
    }
    client.withdraw_offer.return_value = True
    return client


class TestApplicationsCommands:
    @patch("upwork_cli.commands.applications.get_client")
    def test_list_requires_auth(self, MockClient, runner, isolated_config):
        init_db()
        MockClient.side_effect = NotAuthenticated("not authenticated")
        result = runner.invoke(cli, ["applications", "list"])
        assert result.exit_code != 0
        assert "Not authenticated" in result.output

    @patch("upwork_cli.commands.applications.get_client")
    def test_list_happy_path(self, MockClient, runner, isolated_config):
        init_db()
        client = _make_mock_client()
        MockClient.return_value = client
        result = runner.invoke(cli, ["applications", "list", "--limit", "5"])
        assert result.exit_code == 0
        assert "Applications" in result.output
        assert "app-001" in result.output
        client.get_applications.assert_called_with(
            {
                "status": "Accepted",
                "limit": 5,
                "sort_field": "ModifiedDateTime",
                "sort_order": "DESC",
            }
        )

    @patch("upwork_cli.commands.applications.get_client")
    def test_show_happy_path(self, MockClient, runner, isolated_config):
        init_db()
        MockClient.return_value = _make_mock_client()
        result = runner.invoke(cli, ["applications", "show", "app-001"])
        assert result.exit_code == 0
        assert "Application Details" in result.output
        assert "Cover Letter" in result.output
        assert "Related Offers" in result.output

    @patch("upwork_cli.commands.applications.get_client")
    def test_default_group_invokes_list(self, MockClient, runner, isolated_config):
        init_db()
        MockClient.return_value = _make_mock_client()
        result = runner.invoke(cli, ["applications"])
        assert result.exit_code == 0
        assert "Applications" in result.output


class TestOffersCommands:
    @patch("upwork_cli.commands.applications.get_client")
    def test_list_happy_path(self, MockClient, runner, isolated_config):
        init_db()
        client = _make_mock_client()
        MockClient.return_value = client
        result = runner.invoke(cli, ["offers", "list", "--state", "pending"])
        assert result.exit_code == 0
        assert "Offers" in result.output
        assert "offer-001" in result.output
        client.get_offers.assert_called_with({"limit": 20, "state": "Pending"})

    @patch("upwork_cli.commands.applications.get_client")
    def test_show_happy_path(self, MockClient, runner, isolated_config):
        init_db()
        MockClient.return_value = _make_mock_client()
        result = runner.invoke(cli, ["offers", "show", "offer-001"])
        assert result.exit_code == 0
        assert "Backend Retainer" in result.output
        assert "Client Message" in result.output

    @patch("upwork_cli.commands.applications.get_client")
    def test_withdraw_cancelled(self, MockClient, runner, isolated_config):
        init_db()
        client = _make_mock_client()
        MockClient.return_value = client
        result = runner.invoke(cli, ["offers", "withdraw", "offer-001"], input="n\n")
        assert result.exit_code == 0
        assert "Offer not withdrawn" in result.output
        client.withdraw_offer.assert_not_called()

    @patch("upwork_cli.commands.applications.get_client")
    def test_withdraw_with_yes(self, MockClient, runner, isolated_config):
        init_db()
        client = _make_mock_client()
        MockClient.return_value = client
        result = runner.invoke(
            cli,
            [
                "offers",
                "withdraw",
                "offer-001",
                "--reason",
                "no-response",
                "--message",
                "Closing this out on my side.",
                "--yes",
            ],
        )
        assert result.exit_code == 0
        assert "withdrawn successfully" in result.output
        client.withdraw_offer.assert_called_with(
            "offer-001",
            reason="NoResponse",
            message="Closing this out on my side.",
        )
