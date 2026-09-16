"""Tests for the AI proposal learning module."""

import pytest

from tests.fakes import FakeCompleter
from upwork_cli.ai.learner import extract_winning_patterns
from upwork_cli.ai.utils import AIError
from upwork_cli.models import Proposal


def _won(content: str, title: str, tone: str = "professional") -> Proposal:
    return Proposal(
        id=1, job_id="~j", job_title=title, content=content, tone=tone, outcome="won"
    )


class TestExtractWinningPatterns:
    def test_happy_path(self, use_completer):
        use_completer(FakeCompleter("## Opening Patterns\nStart with a hook..."))
        result = extract_winning_patterns([_won("My winning proposal", "Dev")], "key")
        assert "Opening" in result

    def test_every_proposal_reaches_the_model(self, use_completer):
        fake = use_completer(FakeCompleter("Style guide."))
        extract_winning_patterns(
            [_won(f"Proposal {i}", f"Job {i}") for i in range(3)], "key"
        )
        for i in range(3):
            assert f"Proposal {i}" in fake.prompt
            assert f"Job {i}" in fake.prompt

    def test_the_title_fallback_is_the_proposal_type_s(self, use_completer):
        """`Proposal.title` holds it; learner used to default to "unknown"."""
        fake = use_completer(FakeCompleter("ok"))
        extract_winning_patterns([_won("body", "")], "key")
        assert "Untitled" in fake.prompt

    def test_empty_proposals_raises_before_any_call(self, use_completer):
        fake = use_completer(FakeCompleter("ok"))
        with pytest.raises(RuntimeError, match="No winning proposals"):
            extract_winning_patterns([], "key")
        assert fake.calls == []

    def test_api_error_raises(self, use_completer):
        use_completer(FakeCompleter(error=AIError("Anthropic call failed: fail")))
        with pytest.raises(RuntimeError, match="Anthropic call failed"):
            extract_winning_patterns([_won("text", "J")], "key")
