"""Tests for the propose command group's uncovered paths.

`propose generate` with research, `show`, `prep` and `learn` had no coverage
between them. All four go through the AI seam, so all four are driven with a
FakeCompleter rather than a patched vendor class.
"""

import json

import pytest
from click.testing import CliRunner

from tests.fakes import FakeCompleter, FakeUpworkClient, job_node
from upwork_cli import pipeline as pipeline_api
from upwork_cli import proposals as proposals_api
from upwork_cli.ai.utils import AIError
from upwork_cli.cli import cli
from upwork_cli.config import Profile, save_profile
from upwork_cli.db import get_proposals, init_db, upsert_job
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


class TestRecord:
    """Upwork's terms forbid submitting through the API, so every Proposal is
    sent by hand and many are edited on the way. Without this command only AI
    drafts could be stored -- hiding exactly the Proposals `propose learn`
    most needs to see."""

    def _letter(self, tmp_path, text="I diagnosed the 404 before applying."):
        path = tmp_path / "letter.txt"
        path.write_text(text, encoding="utf-8")
        return str(path)

    def test_records_a_hand_written_proposal(self, runner, isolated_config, tmp_path):
        init_db()
        result = runner.invoke(
            cli,
            [
                "propose",
                "record",
                "--from-file",
                self._letter(tmp_path),
                "--title",
                "Fix a podcast RSS feed",
            ],
        )
        assert result.exit_code == 0, result.output
        stored = get_proposals()
        assert len(stored) == 1
        assert stored[0].content == "I diagnosed the 404 before applying."
        assert stored[0].title == "Fix a podcast RSS feed"

    def test_an_outcome_can_be_recorded_at_the_same_time(
        self, runner, isolated_config, tmp_path
    ):
        init_db()
        runner.invoke(
            cli,
            [
                "propose",
                "record",
                "--from-file",
                self._letter(tmp_path),
                "--title",
                "Fix a podcast RSS feed",
                "--outcome",
                "won",
            ],
        )
        assert get_proposals()[0].is_won

    def test_a_won_proposal_moves_its_job_to_won(
        self, runner, isolated_config, tmp_path
    ):
        init_db()
        runner.invoke(
            cli,
            [
                "propose",
                "record",
                "--from-file",
                self._letter(tmp_path),
                "--title",
                "Fix a podcast RSS feed",
                "--outcome",
                "won",
            ],
        )
        stages = {e.job_id: e.stage for e in pipeline_api.entries()}
        assert set(stages.values()) == {"won"}

    def test_a_real_upwork_job_id_is_kept(self, runner, isolated_config, tmp_path):
        """A recorded win has to point at the real posting, not a hash."""
        init_db()
        runner.invoke(
            cli,
            [
                "propose",
                "record",
                "--from-file",
                self._letter(tmp_path),
                "--title",
                "Fix a podcast RSS feed",
                "--job-id",
                "~022094899542523172877",
            ],
        )
        assert get_proposals()[0].job_id == "~022094899542523172877"

    def test_a_cached_job_needs_no_title(self, runner, isolated_config, tmp_path):
        init_db()
        upsert_job(JobPosting(id="~cached", title="Already known"))
        result = runner.invoke(
            cli,
            [
                "propose",
                "record",
                "--from-file",
                self._letter(tmp_path),
                "--job-id",
                "~cached",
            ],
        )
        assert result.exit_code == 0, result.output
        assert get_proposals()[0].title == "Already known"

    def test_an_uncached_job_id_without_a_title_is_refused(
        self, runner, isolated_config, tmp_path
    ):
        init_db()
        result = runner.invoke(
            cli,
            [
                "propose",
                "record",
                "--from-file",
                self._letter(tmp_path),
                "--job-id",
                "~unknown",
            ],
        )
        assert result.exit_code == 1
        assert "--title is needed" in result.output

    def test_neither_title_nor_job_id_is_refused(
        self, runner, isolated_config, tmp_path
    ):
        init_db()
        result = runner.invoke(
            cli, ["propose", "record", "--from-file", self._letter(tmp_path)]
        )
        assert result.exit_code == 1

    def test_an_empty_file_is_refused(self, runner, isolated_config, tmp_path):
        init_db()
        result = runner.invoke(
            cli,
            [
                "propose",
                "record",
                "--from-file",
                self._letter(tmp_path, "   \n"),
                "--title",
                "Anything",
            ],
        )
        assert result.exit_code == 1
        assert "empty" in result.output

    def test_a_recorded_win_reaches_propose_learn(
        self, runner, isolated_config, tmp_path, api_key, use_completer
    ):
        """The point of recording it: `learn` reads won proposals."""
        init_db()
        runner.invoke(
            cli,
            [
                "propose",
                "record",
                "--from-file",
                self._letter(tmp_path, "Diagnosed before applying."),
                "--title",
                "Fix a podcast RSS feed",
                "--outcome",
                "won",
            ],
        )
        fake = use_completer(FakeCompleter("## What works\nDiagnose first."))
        result = runner.invoke(cli, ["propose", "learn"])
        assert result.exit_code == 0, result.output
        assert "Diagnosed before applying." in fake.prompt
