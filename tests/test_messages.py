"""Tests for the messages commands."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from upwork_cli.cli import cli
from upwork_cli.db import init_db


@pytest.fixture
def runner():
    return CliRunner()


def _make_mock_client(authenticated=True):
    """Create a mock UpworkClient with basic stubs."""
    client = MagicMock()
    client.is_authenticated = authenticated
    client.get_user_info.return_value = {"info": {"ref": "~user001"}}
    client.get_companies.return_value = {
        "companies": {
            "company": [{"company_id": "comp-123"}]
        }
    }
    return client


# ---------------------------------------------------------------------------
# Helper tests
# ---------------------------------------------------------------------------


class TestGetCompany:
    @patch("upwork_cli.commands.messages.UpworkClient")
    def test_nested_dict_structure(self, MockClient, runner, isolated_config):
        from upwork_cli.commands.messages import _get_company
        client = _make_mock_client()
        result = _get_company(client)
        assert result == "comp-123"

    @patch("upwork_cli.commands.messages.UpworkClient")
    def test_list_structure(self, MockClient, runner, isolated_config):
        from upwork_cli.commands.messages import _get_company
        client = _make_mock_client()
        client.get_companies.return_value = {
            "companies": [{"company_id": "comp-456"}]
        }
        result = _get_company(client)
        assert result == "comp-456"

    @patch("upwork_cli.commands.messages.UpworkClient")
    def test_empty_raises_system_exit(self, MockClient, runner, isolated_config):
        from upwork_cli.commands.messages import _get_company
        client = _make_mock_client()
        client.get_companies.return_value = {"companies": {"company": []}}
        with pytest.raises(SystemExit):
            _get_company(client)

    @patch("upwork_cli.commands.messages.UpworkClient")
    def test_api_error_raises_system_exit(self, MockClient, runner, isolated_config):
        from upwork_cli.commands.messages import _get_company
        client = _make_mock_client()
        client.get_companies.side_effect = Exception("API error")
        with pytest.raises(SystemExit):
            _get_company(client)


class TestGetUserId:
    @patch("upwork_cli.commands.messages.UpworkClient")
    def test_happy_path(self, MockClient, runner, isolated_config):
        from upwork_cli.commands.messages import _get_user_id
        client = _make_mock_client()
        result = _get_user_id(client)
        assert result == "~user001"

    @patch("upwork_cli.commands.messages.UpworkClient")
    def test_error_returns_empty(self, MockClient, runner, isolated_config):
        from upwork_cli.commands.messages import _get_user_id
        client = _make_mock_client()
        client.get_user_info.side_effect = Exception("fail")
        result = _get_user_id(client)
        assert result == ""


# ---------------------------------------------------------------------------
# List rooms
# ---------------------------------------------------------------------------


class TestListRooms:
    @patch("upwork_cli.commands.messages.UpworkClient")
    def test_not_authenticated(self, MockClient, runner, isolated_config):
        init_db()
        MockClient.return_value = _make_mock_client(authenticated=False)
        result = runner.invoke(cli, ["messages", "list"])
        assert result.exit_code != 0
        assert "Not authenticated" in result.output

    @patch("upwork_cli.commands.messages.UpworkClient")
    def test_happy_path(self, MockClient, runner, isolated_config):
        init_db()
        client = _make_mock_client()
        client.get_rooms.return_value = {
            "rooms": [
                {
                    "roomId": "room-001",
                    "roster": [{"name": "Alice"}, {"name": "Bob"}],
                    "recentMessage": {"message": "Hello there!"},
                    "roomUpdatedDate": "2025-01-15T10:00:00Z",
                }
            ]
        }
        MockClient.return_value = client
        result = runner.invoke(cli, ["messages", "list"])
        assert result.exit_code == 0
        assert "Recent Conversations" in result.output
        assert "room-001" in result.output

    @patch("upwork_cli.commands.messages.UpworkClient")
    def test_empty_rooms(self, MockClient, runner, isolated_config):
        init_db()
        client = _make_mock_client()
        client.get_rooms.return_value = {"rooms": []}
        MockClient.return_value = client
        result = runner.invoke(cli, ["messages", "list"])
        assert result.exit_code == 0
        assert "No conversations" in result.output

    @patch("upwork_cli.commands.messages.UpworkClient")
    def test_dict_normalization(self, MockClient, runner, isolated_config):
        """Rooms API sometimes returns a dict instead of a list for single room."""
        init_db()
        client = _make_mock_client()
        client.get_rooms.return_value = {
            "rooms": {
                "room": [
                    {
                        "roomId": "room-single",
                        "roster": [{"name": "Solo"}],
                        "recentMessage": {"message": "Hi"},
                        "roomUpdatedDate": "2025-01-15",
                    }
                ]
            }
        }
        MockClient.return_value = client
        result = runner.invoke(cli, ["messages", "list"])
        assert result.exit_code == 0
        assert "room-single" in result.output

    @patch("upwork_cli.commands.messages.UpworkClient")
    def test_limit_param(self, MockClient, runner, isolated_config):
        init_db()
        client = _make_mock_client()
        client.get_rooms.return_value = {"rooms": []}
        MockClient.return_value = client
        result = runner.invoke(cli, ["messages", "list", "--limit", "5"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Read messages
# ---------------------------------------------------------------------------


class TestReadMessages:
    @patch("upwork_cli.commands.messages.UpworkClient")
    def test_happy_path(self, MockClient, runner, isolated_config):
        init_db()
        client = _make_mock_client()
        client.get_room_messages.return_value = {
            "stories": [
                {
                    "userId": "~other",
                    "user": {"name": "Alice"},
                    "message": "Can you start today?",
                    "created_time": "2025-01-15T10:00:00Z",
                },
                {
                    "userId": "~user001",
                    "user": {"name": "Me"},
                    "message": "Sure thing!",
                    "created_time": "2025-01-15T10:05:00Z",
                },
            ]
        }
        MockClient.return_value = client
        result = runner.invoke(cli, ["messages", "read", "room-001"])
        assert result.exit_code == 0
        assert "room-001" in result.output

    @patch("upwork_cli.commands.messages.UpworkClient")
    def test_empty_stories(self, MockClient, runner, isolated_config):
        init_db()
        client = _make_mock_client()
        client.get_room_messages.return_value = {"stories": []}
        MockClient.return_value = client
        result = runner.invoke(cli, ["messages", "read", "room-empty"])
        assert result.exit_code == 0
        assert "No messages" in result.output

    @patch("upwork_cli.commands.messages.UpworkClient")
    def test_dict_normalization(self, MockClient, runner, isolated_config):
        """Messages API sometimes returns a dict wrapping for stories."""
        init_db()
        client = _make_mock_client()
        client.get_room_messages.return_value = {
            "stories": {
                "story": [
                    {
                        "userId": "~other",
                        "user": {"name": "Alice"},
                        "message": "Hello",
                        "created_time": "2025-01-15",
                    }
                ]
            }
        }
        MockClient.return_value = client
        result = runner.invoke(cli, ["messages", "read", "room-dict"])
        assert result.exit_code == 0

    @patch("upwork_cli.commands.messages.UpworkClient")
    def test_api_error(self, MockClient, runner, isolated_config):
        init_db()
        client = _make_mock_client()
        client.get_room_messages.side_effect = Exception("API down")
        MockClient.return_value = client
        result = runner.invoke(cli, ["messages", "read", "room-fail"])
        assert result.exit_code != 0
        assert "Failed to fetch messages" in result.output


# ---------------------------------------------------------------------------
# Send message
# ---------------------------------------------------------------------------


class TestSendMessage:
    @patch("upwork_cli.commands.messages.UpworkClient")
    def test_success_with_confirm(self, MockClient, runner, isolated_config):
        init_db()
        client = _make_mock_client()
        client.send_message.return_value = {}
        MockClient.return_value = client
        result = runner.invoke(
            cli, ["messages", "send", "room-001", "Hello!"], input="y\n"
        )
        assert result.exit_code == 0
        assert "sent successfully" in result.output

    @patch("upwork_cli.commands.messages.UpworkClient")
    def test_user_cancels(self, MockClient, runner, isolated_config):
        init_db()
        client = _make_mock_client()
        MockClient.return_value = client
        result = runner.invoke(
            cli, ["messages", "send", "room-001", "Hello!"], input="n\n"
        )
        assert result.exit_code == 0
        assert "not sent" in result.output

    @patch("upwork_cli.commands.messages.UpworkClient")
    def test_api_error(self, MockClient, runner, isolated_config):
        init_db()
        client = _make_mock_client()
        client.send_message.side_effect = Exception("Network error")
        MockClient.return_value = client
        result = runner.invoke(
            cli, ["messages", "send", "room-001", "Hello!"], input="y\n"
        )
        assert result.exit_code != 0
        assert "Failed to send" in result.output


# ---------------------------------------------------------------------------
# Find room
# ---------------------------------------------------------------------------


class TestFindRoom:
    @patch("upwork_cli.commands.messages.UpworkClient")
    def test_found_with_messages(self, MockClient, runner, isolated_config):
        init_db()
        client = _make_mock_client()
        client.get_room_by_contract.return_value = {
            "room": {"roomId": "room-found"}
        }
        client.get_room_messages.return_value = {
            "stories": [
                {
                    "userId": "~other",
                    "user": {"name": "Alice"},
                    "message": "Let's discuss scope.",
                    "created_time": "2025-01-15",
                }
            ]
        }
        MockClient.return_value = client
        result = runner.invoke(cli, ["messages", "find", "--contract", "~eng001"])
        assert result.exit_code == 0
        assert "room-found" in result.output

    @patch("upwork_cli.commands.messages.UpworkClient")
    def test_not_found(self, MockClient, runner, isolated_config):
        init_db()
        client = _make_mock_client()
        client.get_room_by_contract.return_value = {"room": {}}
        MockClient.return_value = client
        result = runner.invoke(cli, ["messages", "find", "--contract", "~eng999"])
        assert result.exit_code == 0
        assert "No room found" in result.output

    @patch("upwork_cli.commands.messages.UpworkClient")
    def test_api_error(self, MockClient, runner, isolated_config):
        init_db()
        client = _make_mock_client()
        client.get_room_by_contract.side_effect = Exception("fail")
        MockClient.return_value = client
        result = runner.invoke(cli, ["messages", "find", "--contract", "~eng001"])
        assert result.exit_code != 0
        assert "Failed to find room" in result.output
