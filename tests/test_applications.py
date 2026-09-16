"""CLI-level tests for the applications and offers command groups.

Payload handling is covered in test_applications_module.py through the
module's own interface. What is left here is what the commands decide:
rendering, confirmation prompts, exit codes and empty states.
"""

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from tests.fakes import FakeUpworkClient, application_node, connection, offer_node
from upwork_cli.cli import cli
from upwork_cli.client import NotAuthenticated


@pytest.fixture
def runner():
    # Wide enough that Rich renders table cells in full: two no-wrap
    # timestamp columns otherwise squeeze the Job column to an ellipsis.
    return CliRunner(env={"COLUMNS": "200"})


def _run(runner, args, client=None, input=None, **fake_kwargs):
    """Invoke the CLI with a fake client behind the single construction site."""
    client = client if client is not None else FakeUpworkClient(**fake_kwargs)
    with patch("upwork_cli.commands.applications.get_client", return_value=client):
        return runner.invoke(cli, args, input=input)


class TestAuthentication:
    def test_unauthenticated_reports_and_exits(self, runner, isolated_config):
        with patch(
            "upwork_cli.commands.applications.get_client",
            side_effect=NotAuthenticated("nope"),
        ):
            result = runner.invoke(cli, ["applications", "list"])
        assert result.exit_code == 1
        assert "Not authenticated" in result.output


class TestApplicationsCommands:
    def test_list_renders_a_table(self, runner, isolated_config):
        result = _run(
            runner,
            ["applications", "list"],
            applications=connection(
                application_node("app-1", job_title="Build an API", status="Submitted")
            ),
        )
        assert result.exit_code == 0
        assert "app-1" in result.output
        assert "Build an API" in result.output
        assert "Submitted" in result.output

    def test_list_empty_state(self, runner, isolated_config):
        result = _run(runner, ["applications", "list"], applications=connection())
        assert result.exit_code == 0
        assert "No applications found" in result.output

    def test_list_api_failure(self, runner, isolated_config):
        result = _run(
            runner, ["applications", "list"], applications=RuntimeError("boom")
        )
        assert result.exit_code == 1
        assert "fetch applications" in result.output

    def test_default_group_invokes_list(self, runner, isolated_config):
        result = _run(
            runner,
            ["applications"],
            applications=connection(application_node("app-1")),
        )
        assert result.exit_code == 0
        assert "app-1" in result.output

    def test_show_renders_details_and_cover_letter(self, runner, isolated_config):
        result = _run(
            runner,
            ["applications", "show", "app-1"],
            application=application_node(
                "app-1", job_title="Build an API", cover_letter="Pick me."
            ),
            offers_for_application=[offer_node("offer-1")],
        )
        assert result.exit_code == 0
        assert "Build an API" in result.output
        assert "Pick me." in result.output
        assert "$3,000.00 USD" in result.output
        assert "offer-1" in result.output

    def test_show_missing_application(self, runner, isolated_config):
        result = _run(runner, ["applications", "show", "nope"], application={})
        assert result.exit_code == 1
        assert "was not found" in result.output


class TestOffersCommands:
    def test_list_renders_a_table(self, runner, isolated_config):
        result = _run(
            runner,
            ["offers", "list"],
            offers=connection(
                offer_node("offer-1", title="Backend work", client_name="Acme Corp")
            ),
        )
        assert result.exit_code == 0
        assert "offer-1" in result.output
        assert "Acme Corp" in result.output

    def test_list_empty_state(self, runner, isolated_config):
        result = _run(runner, ["offers", "list"], offers=connection())
        assert result.exit_code == 0
        assert "No offers found" in result.output

    def test_show_renders_fixed_price_terms(self, runner, isolated_config):
        result = _run(
            runner, ["offers", "show", "offer-1"], offer=offer_node(budget="5000")
        )
        assert result.exit_code == 0
        assert "$5,000.00 USD" in result.output

    def test_show_renders_hourly_terms_with_a_cap(self, runner, isolated_config):
        result = _run(
            runner,
            ["offers", "show", "offer-1"],
            offer=offer_node(budget=None, hourly_rate="85", weekly_limit=30),
        )
        assert "$85.00 USD / 30 hrs" in result.output

    def test_show_missing_offer(self, runner, isolated_config):
        result = _run(runner, ["offers", "show", "nope"], offer={})
        assert result.exit_code == 1
        assert "was not found" in result.output

    def test_withdraw_cancelled(self, runner, isolated_config):
        client = FakeUpworkClient()
        result = _run(
            runner, ["offers", "withdraw", "offer-1"], client=client, input="n\n"
        )
        assert result.exit_code == 0
        assert client.withdrawn == []
        assert "not withdrawn" in result.output

    def test_withdraw_with_yes_skips_the_prompt(self, runner, isolated_config):
        client = FakeUpworkClient()
        result = _run(
            runner,
            ["offers", "withdraw", "offer-1", "--yes", "--reason", "other"],
            client=client,
        )
        assert result.exit_code == 0
        assert client.withdrawn == [("offer-1", "Other", None)]
        assert "withdrawn successfully" in result.output

    def test_withdraw_passes_the_message_through(self, runner, isolated_config):
        client = FakeUpworkClient()
        _run(
            runner,
            ["offers", "withdraw", "offer-1", "--yes", "--message", "changed my mind"],
            client=client,
        )
        assert client.withdrawn[0][2] == "changed my mind"
