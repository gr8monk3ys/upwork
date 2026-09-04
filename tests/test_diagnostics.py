"""Tests for `upwork doctor`.

The command exists because coverage measures agreement with the fakes, not
with Upwork. These tests necessarily use the fakes too -- what they pin is
that the diagnostic reports rather than aborts, and that a working account
and a broken one are told apart.
"""

import pytest
from click.testing import CliRunner

from tests.fakes import (
    FakeCompleter,
    FakeUpworkClient,
    connection,
    earnings_payload,
    engagement_node,
    job_search_payload,
    room_payload,
)
from upwork_cli import diagnostics
from upwork_cli.cli import cli
from upwork_cli.client import NotAuthenticated
from upwork_cli.config import Profile, Settings, save_profile, save_settings


@pytest.fixture
def runner():
    return CliRunner(env={"COLUMNS": "200"})


@pytest.fixture
def healthy_client():
    return FakeUpworkClient(
        search_results=job_search_payload(),
        applications=connection(),
        offers=connection(),
        earnings=earnings_payload(),
        engagements={"engagement": [engagement_node()]},
        rooms=room_payload(),
    )


def _configured(monkeypatch, **kw):
    monkeypatch.setenv("UPWORK_CLIENT_SECRET", "secret")
    save_settings(Settings(client_id="cid", **kw))


class TestConfiguration:
    def test_missing_credentials_fail(self, isolated_config):
        checks = {c.name: c for c in diagnostics.configuration()}
        assert checks["Upwork credentials"].status == diagnostics.FAILED
        assert "config setup" in checks["Upwork credentials"].detail

    def test_a_missing_ai_key_is_skipped_not_failed(self, isolated_config):
        """No AI key is a working install with fewer features, not a fault."""
        checks = {c.name: c for c in diagnostics.configuration()}
        assert checks["Anthropic API key"].status == diagnostics.SKIPPED

    def test_an_empty_profile_is_skipped_not_failed(self, isolated_config):
        checks = {c.name: c for c in diagnostics.configuration()}
        assert checks["Profile"].status == diagnostics.SKIPPED

    def test_a_configured_install_passes(self, isolated_config, monkeypatch):
        _configured(monkeypatch)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
        save_profile(Profile(title="Python dev"))
        checks = {c.name: c for c in diagnostics.configuration()}
        assert all(c.status == diagnostics.OK for c in checks.values())


class TestUpworkApi:
    def test_every_path_is_exercised(self, isolated_config, healthy_client):
        checks = diagnostics.upwork_api(healthy_client)
        assert [c.name for c in checks] == [
            "Authentication",
            "Job search",
            "Applications",
            "Offers",
            "Earnings report",
            "Contracts",
            "Messages",
        ]
        assert all(not c.failed for c in checks), [c for c in checks if c.failed]

    def test_one_broken_path_does_not_stop_the_others(self, isolated_config):
        """The point is to learn everything broken in one run."""
        client = FakeUpworkClient(
            search_results=RuntimeError("search is down"),
            applications=connection(),
            offers=connection(),
            earnings=earnings_payload(),
            engagements={"engagement": []},
            rooms=room_payload(),
        )
        checks = {c.name: c for c in diagnostics.upwork_api(client)}
        assert checks["Job search"].failed
        assert "search is down" in checks["Job search"].detail
        assert not checks["Applications"].failed
        assert not checks["Messages"].failed

    def test_an_empty_account_is_not_a_failure(self, isolated_config):
        """No contracts is a working account, not a broken one."""
        client = FakeUpworkClient(
            search_results=job_search_payload(),
            applications=connection(),
            offers=connection(),
            earnings=earnings_payload(),
            engagements={},
            rooms=room_payload(),
        )
        checks = {c.name: c for c in diagnostics.upwork_api(client)}
        assert checks["Contracts"].status == diagnostics.OK
        assert "0 contracts" in checks["Contracts"].detail


class TestRunAll:
    def test_unauthenticated_stops_before_the_api_checks(
        self, isolated_config, monkeypatch
    ):
        monkeypatch.setattr(
            "upwork_cli.diagnostics.get_client",
            lambda: (_ for _ in ()).throw(NotAuthenticated("Not authenticated.")),
        )
        checks = diagnostics.run_all(with_ai=False)
        assert checks[-1].name == "Authentication"
        assert checks[-1].failed
        assert "Job search" not in [c.name for c in checks]

    def test_ai_is_checked_only_when_a_key_exists(
        self, isolated_config, monkeypatch, healthy_client, use_completer
    ):
        _configured(monkeypatch)
        monkeypatch.setattr("upwork_cli.diagnostics.get_client", lambda: healthy_client)
        assert "Anthropic completion" not in [
            c.name for c in diagnostics.run_all(with_ai=True)
        ]

        monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
        use_completer(FakeCompleter("ok"))
        names = [c.name for c in diagnostics.run_all(with_ai=True)]
        assert "Anthropic completion" in names

    def test_no_ai_flag_skips_the_completion(
        self, isolated_config, monkeypatch, healthy_client
    ):
        _configured(monkeypatch)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
        monkeypatch.setattr("upwork_cli.diagnostics.get_client", lambda: healthy_client)
        names = [c.name for c in diagnostics.run_all(with_ai=False)]
        assert "Anthropic completion" not in names


class TestDoctorCommand:
    def test_a_healthy_install_exits_zero(
        self, runner, isolated_config, monkeypatch, healthy_client
    ):
        _configured(monkeypatch)
        save_profile(Profile(title="Python dev"))
        monkeypatch.setattr("upwork_cli.diagnostics.get_client", lambda: healthy_client)
        result = runner.invoke(cli, ["doctor", "--no-ai"])
        assert result.exit_code == 0, result.output
        assert "checks passed" in result.output

    def test_a_broken_install_exits_one_and_names_what_failed(
        self, runner, isolated_config
    ):
        result = runner.invoke(cli, ["doctor"])
        assert result.exit_code == 1
        assert "Upwork credentials" in result.output
        assert "Authentication" in result.output


class TestAuthenticationRemedy:
    """`config setup` re-prompts for five credentials before reaching OAuth.
    When only the token is missing, `config login` is the smaller answer."""

    def _unauthenticated(self, monkeypatch):
        monkeypatch.setattr(
            "upwork_cli.diagnostics.get_client",
            lambda: (_ for _ in ()).throw(NotAuthenticated("no token")),
        )

    def test_with_credentials_it_points_at_login(self, isolated_config, monkeypatch):
        _configured(monkeypatch)
        self._unauthenticated(monkeypatch)
        auth = [
            c for c in diagnostics.run_all(with_ai=False) if c.name == "Authentication"
        ]
        assert auth[0].failed
        assert "config login" in auth[0].detail

    def test_without_credentials_it_points_at_setup(self, isolated_config, monkeypatch):
        self._unauthenticated(monkeypatch)
        auth = [
            c for c in diagnostics.run_all(with_ai=False) if c.name == "Authentication"
        ]
        assert "config setup" in auth[0].detail


class TestConfigLogin:
    def test_login_refuses_without_credentials(self, runner, isolated_config):
        result = runner.invoke(cli, ["config", "login"])
        assert result.exit_code == 1
        assert "not configured" in result.output
        assert "config setup" in result.output
