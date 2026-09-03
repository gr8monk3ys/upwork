"""CLI-level tests for the messages command group.

Payload handling is covered in test_messaging.py through the module's own
interface. What is left here is what the commands themselves decide:
rendering, confirmation prompts, exit codes and empty states.
"""

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from tests.fakes import FakeUpworkClient, message_payload, room_payload
from upwork_cli.cli import cli
from upwork_cli.client import NotAuthenticated


@pytest.fixture
def runner():
    return CliRunner()


def _run(runner, args, client=None, **fake_kwargs):
    """Invoke the CLI with a fake client behind the single construction site."""
    client = client if client is not None else FakeUpworkClient(**fake_kwargs)
    with patch("upwork_cli.commands.messages.get_client", return_value=client):
        return runner.invoke(cli, args)


class TestAuthentication:
    def test_unauthenticated_reports_and_exits(self, runner, isolated_config):
        with patch(
            "upwork_cli.commands.messages.get_client",
            side_effect=NotAuthenticated("nope"),
        ):
            result = runner.invoke(cli, ["messages", "list"])
        assert result.exit_code == 1
        assert "Not authenticated" in result.output


class TestListRooms:
    def test_renders_a_table(self, runner, isolated_config):
        result = _run(
            runner,
            ["messages", "list"],
            rooms={"rooms": [room_payload("r-1", participants=["Dana Reyes"])]},
        )
        assert result.exit_code == 0
        assert "r-1" in result.output
        assert "Dana Reyes" in result.output
        assert "Hello there" in result.output

    def test_empty_state(self, runner, isolated_config):
        result = _run(runner, ["messages", "list"], rooms={"rooms": []})
        assert result.exit_code == 0
        assert "No conversations found" in result.output

    def test_api_failure_exits_nonzero(self, runner, isolated_config):
        result = _run(runner, ["messages", "list"], rooms=RuntimeError("boom"))
        assert result.exit_code == 1
        assert "fetch rooms" in result.output


class TestReadMessages:
    def test_marks_own_messages(self, runner, isolated_config):
        result = _run(
            runner,
            ["messages", "read", "r-1"],
            user_id="~me",
            messages={
                "stories": [
                    message_payload("m1", sender_id="~me", sender_name="Me"),
                    message_payload("m2", sender_id="~them", sender_name="Dana Reyes"),
                ]
            },
        )
        assert result.exit_code == 0
        assert "(you)" in result.output
        assert "Dana Reyes" in result.output

    def test_shows_names_not_ids(self, runner, isolated_config):
        """Regression: the sender's raw user id used to be displayed."""
        result = _run(
            runner,
            ["messages", "read", "r-1"],
            messages={
                "stories": [
                    message_payload(sender_id="~01ab99", sender_name="Dana Reyes")
                ]
            },
        )
        assert "Dana Reyes" in result.output
        assert "~01ab99" not in result.output

    def test_empty_state(self, runner, isolated_config):
        result = _run(runner, ["messages", "read", "r-1"], messages={"stories": []})
        assert result.exit_code == 0
        assert "No messages found" in result.output

    def test_api_failure_exits_nonzero(self, runner, isolated_config):
        result = _run(
            runner, ["messages", "read", "r-1"], messages=RuntimeError("nope")
        )
        assert result.exit_code == 1


class TestSendMessage:
    def test_confirmed_send_reaches_the_client(self, runner, isolated_config):
        client = FakeUpworkClient()
        with patch("upwork_cli.commands.messages.get_client", return_value=client):
            result = runner.invoke(
                cli, ["messages", "send", "r-1", "hello"], input="y\n"
            )
        assert result.exit_code == 0
        assert client.sent == [("comp-123", "r-1", {"message": "hello"})]
        assert "Message sent successfully" in result.output

    def test_declined_send_does_nothing(self, runner, isolated_config):
        client = FakeUpworkClient()
        with patch("upwork_cli.commands.messages.get_client", return_value=client):
            result = runner.invoke(cli, ["messages", "send", "r-1", "hi"], input="n\n")
        assert result.exit_code == 0
        assert client.sent == []
        assert "not sent" in result.output.lower()


class TestFindRoom:
    def test_found_with_messages(self, runner, isolated_config):
        result = _run(
            runner,
            ["messages", "find", "--contract", "c-1"],
            room_by_contract={"room": room_payload("r-7")},
            messages={"stories": [message_payload(text="Latest news")]},
        )
        assert result.exit_code == 0
        assert "r-7" in result.output
        assert "Latest news" in result.output

    def test_not_found(self, runner, isolated_config):
        result = _run(
            runner,
            ["messages", "find", "--contract", "c-1"],
            room_by_contract={"room": {}},
        )
        assert result.exit_code == 0
        assert "No room found" in result.output

    def test_api_failure_exits_nonzero(self, runner, isolated_config):
        result = _run(
            runner,
            ["messages", "find", "--contract", "c-1"],
            room_by_contract=RuntimeError("gone"),
        )
        assert result.exit_code == 1
