"""Tests for the propose command group's uncovered paths.

`propose generate` with research, `show`, `prep` and `learn` had no coverage
between them. All four go through the AI seam, so all four are driven with a
FakeCompleter rather than a patched vendor class.
"""

import json

import pytest
from click.testing import CliRunner

from tests.fakes import FakeCompleter, FakeUpworkClient, job_node
from upwork_cli import proposals as proposals_api
from upwork_cli.ai.utils import AIError
from upwork_cli.cli import cli
from upwork_cli.config import Profile, save_profile
from upwork_cli.db import init_db, upsert_job
from upwork_cli.models import JobPosting

RESEARCH_JSON = json.dumps(
    {
        "risk_level": "low",
        "spending_tier": "large",
        "brief": "Long-standing client, pays promptly.",
        "proposal_tips": "Lead with the integration work.",
    }
)


@pytest.fixture
def runner():
    return CliRunner(env={"COLUMNS": "200"})


@pytest.fixture
def api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")


@pytest.fixture
def cached_job(isolated_config):
    init_db()
    save_profile(Profile(title="Python dev", skills=["Python"]))
    posting = JobPosting(
        id="~job1",
        title="Build a scraper",
        description="We need a scraper.",
        client_total_spent=150000.0,
        client_country="US",
    )
    upsert_job(posting)
    return posting


class TestGenerateWithResearch:
    def test_research_reaches_the_draft(
        self, runner, cached_job, api_key, use_completer
    ):
        fake = use_completer(FakeCompleter(RESEARCH_JSON, "Here is the proposal."))
        result = runner.invoke(cli, ["propose", "generate", "~job1", "--research"])
        assert result.exit_code == 0, result.output
        assert "Client Research" in result.output
        assert "pays promptly" in result.output
        # the research tips are appended to what the drafter is given
        assert "Lead with the integration work." in fake.calls[-1]["prompt"]

    def test_a_failed_research_degrades_rather_than_aborting(
        self, runner, cached_job, api_key, use_completer
    ):
        """The proposal is still drafted; the user is told research was skipped."""

        def responder(prompt: str) -> str:
            if "risk_level" in prompt or "spending_tier" in prompt:
                raise AIError("research model down")
            return "Here is the proposal anyway."

        use_completer(FakeCompleter(responder=responder))
        result = runner.invoke(cli, ["propose", "generate", "~job1", "--research"])
        assert result.exit_code == 0, result.output
        assert "Client research failed" in result.output
        assert "Here is the proposal anyway." in result.output

    def test_no_research_flag_makes_no_research_call(
        self, runner, cached_job, api_key, use_completer
    ):
        fake = use_completer(FakeCompleter("Just the proposal."))
        runner.invoke(cli, ["propose", "generate", "~job1", "--no-research"])
        assert len(fake.calls) == 1

    def test_an_uncached_job_is_fetched_through_the_jobs_seam(
        self, runner, isolated_config, api_key, use_completer, monkeypatch
    ):
        init_db()
        save_profile(Profile(title="Python dev"))
        monkeypatch.setattr(
            "upwork_cli.commands.propose.get_client",
            lambda: FakeUpworkClient(
                job_detail=job_node("~remote", title="Remote job")
            ),
        )
        use_completer(FakeCompleter("Drafted."))
        result = runner.invoke(cli, ["propose", "generate", "~remote", "--no-research"])
        assert result.exit_code == 0, result.output
        assert "Fetching from API" in result.output


class TestShow:
    def _stored(self):
        return proposals_api.record("~job1", "Build a scraper", "My letter.", "casual")

    def test_shows_the_stored_proposal(self, runner, cached_job):
        stored = self._stored()
        result = runner.invoke(cli, ["propose", "show", str(stored.id)])
        assert result.exit_code == 0
        assert "My letter." in result.output
        assert "casual" in result.output

    def test_an_unknown_id_fails(self, runner, cached_job):
        result = runner.invoke(cli, ["propose", "show", "999"])
        assert result.exit_code == 1
        assert "not found" in result.output


class TestPrep:
    def test_generates_interview_prep_for_a_cached_job(
        self, runner, cached_job, api_key, use_completer
    ):
        use_completer(FakeCompleter("## Likely questions\n1. Why you?"))
        result = runner.invoke(cli, ["propose", "prep", "~job1"])
        assert result.exit_code == 0, result.output
        assert "Likely questions" in result.output

    def test_an_uncached_job_fails(self, runner, isolated_config, api_key):
        init_db()
        result = runner.invoke(cli, ["propose", "prep", "~nope"])
        assert result.exit_code == 1
        assert "not found in local cache" in result.output


class TestLearn:
    def test_extracts_patterns_from_won_proposals(
        self, runner, cached_job, api_key, use_completer
    ):
        stored = proposals_api.record("~job1", "Build a scraper", "Winner.", "casual")
        proposals_api.mark(stored.id, "won")
        use_completer(FakeCompleter("## What works\nLead with results."))
        result = runner.invoke(cli, ["propose", "learn"])
        assert result.exit_code == 0, result.output
        assert "Lead with results." in result.output

    def test_no_won_proposals_reports_rather_than_calling_the_model(
        self, runner, cached_job, api_key, use_completer
    ):
        fake = use_completer(FakeCompleter("unused"))
        result = runner.invoke(cli, ["propose", "learn"])
        assert fake.calls == []
        assert "won" in result.output.lower() or "no " in result.output.lower()
