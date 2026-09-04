"""Tests for the AI interview prep module."""

import pytest

from tests.fakes import FakeCompleter
from upwork_cli.ai.interview_prep import generate_interview_prep
from upwork_cli.ai.utils import AIError


class TestInterviewPrep:
    def test_happy_path(self, use_completer):
        use_completer(FakeCompleter("## Likely Questions\n1. Tell me about..."))
        assert "Questions" in generate_interview_prep("job", "profile", "key")

    def test_the_job_and_profile_reach_the_model(self, use_completer):
        fake = use_completer(FakeCompleter("ok"))
        generate_interview_prep("scrape a site", "python dev", "key")
        assert "scrape a site" in fake.prompt
        assert "python dev" in fake.prompt

    def test_client_research_reaches_the_model_when_given(self, use_completer):
        fake = use_completer(FakeCompleter("Prep notes with research context."))
        result = generate_interview_prep(
            "job", "profile", "key", client_research="Low risk client"
        )
        assert "Prep notes" in result
        assert "Low risk client" in fake.prompt

    def test_raises_on_error(self, use_completer):
        use_completer(FakeCompleter(error=AIError("Anthropic call failed: API down")))
        with pytest.raises(RuntimeError, match="Anthropic call failed"):
            generate_interview_prep("job", "profile", "key")
