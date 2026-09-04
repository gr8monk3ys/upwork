"""Tests for the AI proposal drafting module upwork_cli.ai.drafter.

Driven through the AI seam with a FakeCompleter. Translating Anthropic's own
exceptions into AIError is `AnthropicCompleter`'s job and is tested once, in
test_ai_utils.py; what matters here is that drafter passes the right prompt
and lets the error through.
"""

import pytest

from tests.fakes import FakeCompleter
from upwork_cli.ai.drafter import draft_proposal, refine_proposal
from upwork_cli.ai.utils import AIError


class TestDraftProposal:
    def test_happy_path(self, use_completer):
        use_completer(FakeCompleter("Here is your tailored proposal."))
        assert (
            draft_proposal("job summary", "profile", "fake-key")
            == "Here is your tailored proposal."
        )

    def test_the_job_and_profile_reach_the_model(self, use_completer):
        fake = use_completer(FakeCompleter("ok"))
        draft_proposal("build a scraper", "senior python dev", "key")
        assert "build a scraper" in fake.prompt
        assert "senior python dev" in fake.prompt

    def test_model_passed_through(self, use_completer):
        fake = use_completer(FakeCompleter("ok"))
        draft_proposal("job", "profile", "key", model="claude-haiku-4-5")
        assert fake.calls[-1]["model"] == "claude-haiku-4-5"

    def test_tone_reaches_the_model_as_a_system_prompt(self, use_completer):
        fake = use_completer(FakeCompleter("ok"))
        draft_proposal("job", "profile", "key", tone="technical")
        assert "technical" in fake.calls[-1]["system"]

    def test_invalid_tone_raises_before_any_call(self, use_completer):
        fake = use_completer(FakeCompleter("ok"))
        with pytest.raises(ValueError, match="Invalid tone"):
            draft_proposal("job", "profile", "key", tone="angry")
        assert fake.calls == []

    def test_invalid_length_raises_before_any_call(self, use_completer):
        fake = use_completer(FakeCompleter("ok"))
        with pytest.raises(ValueError, match="Invalid length"):
            draft_proposal("job", "profile", "key", length="huge")
        assert fake.calls == []

    def test_an_api_failure_reaches_the_caller(self, use_completer):
        use_completer(FakeCompleter(error=AIError("Invalid Anthropic API key.")))
        with pytest.raises(AIError, match="Invalid Anthropic API key"):
            draft_proposal("job", "profile", "bad-key")


class TestRefineProposal:
    def test_refine_returns_text(self, use_completer):
        use_completer(FakeCompleter("Refined proposal text."))
        assert (
            refine_proposal("draft", "make it shorter", "key")
            == "Refined proposal text."
        )

    def test_the_draft_and_feedback_reach_the_model(self, use_completer):
        fake = use_completer(FakeCompleter("ok"))
        refine_proposal("my first draft", "make it shorter", "key")
        assert "my first draft" in fake.prompt
        assert "make it shorter" in fake.prompt

    def test_an_api_failure_reaches_the_caller(self, use_completer):
        use_completer(FakeCompleter(error=AIError("rate limit reached")))
        with pytest.raises(AIError, match="rate limit"):
            refine_proposal("draft", "shorter", "key")
