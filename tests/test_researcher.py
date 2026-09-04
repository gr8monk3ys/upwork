"""Tests for the AI client research module."""

import json

import pytest

from tests.fakes import FakeCompleter
from upwork_cli.ai.researcher import research_client
from upwork_cli.ai.utils import AIError

SAMPLE_JSON = json.dumps(
    {
        "risk_level": "low",
        "spending_tier": "large",
        "brief": "Well-established client with strong track record.",
        "proposal_tips": "Emphasize reliability and past results.",
    }
)


class TestResearchClient:
    def test_happy_path(self, use_completer):
        use_completer(FakeCompleter(SAMPLE_JSON))
        result = research_client("job", 150000, 42, 4.9, "US", True, "key")
        assert result["risk_level"] == "low"
        assert result["spending_tier"] == "large"

    def test_fenced_json(self, use_completer):
        use_completer(FakeCompleter(f"```json\n{SAMPLE_JSON}\n```"))
        result = research_client("job", None, None, None, "", False, "key")
        assert result["risk_level"] == "low"

    def test_the_client_facts_reach_the_model(self, use_completer):
        fake = use_completer(FakeCompleter(SAMPLE_JSON))
        research_client("build a scraper", 150000, 42, 4.9, "US", True, "key")
        assert "build a scraper" in fake.prompt
        assert "150,000" in fake.prompt or "150000" in fake.prompt

    def test_api_error_raises(self, use_completer):
        use_completer(FakeCompleter(error=AIError("Anthropic call failed: fail")))
        with pytest.raises(AIError):
            research_client("job", None, None, None, "", False, "key")

    def test_unparseable_response_raises(self, use_completer):
        """Was a silent canned fallback; the caller degrades on the error
        instead, so the user is told why research was skipped."""
        use_completer(FakeCompleter("not json"))
        with pytest.raises(AIError, match="client analysis"):
            research_client("job", None, None, None, "", False, "key")

    def test_non_object_response_raises(self, use_completer):
        use_completer(FakeCompleter("[1, 2, 3]"))
        with pytest.raises(AIError, match="not a JSON object"):
            research_client("job", None, None, None, "", False, "key")

    def test_invalid_values_normalized(self, use_completer):
        use_completer(
            FakeCompleter(
                json.dumps(
                    {
                        "risk_level": "catastrophic",
                        "spending_tier": "galactic",
                        "brief": 42,
                        "proposal_tips": None,
                    }
                )
            )
        )
        result = research_client("job", None, None, None, "", False, "key")
        assert result["risk_level"] == "unknown"
        assert result["spending_tier"] == "unknown"
        assert isinstance(result["brief"], str)
        assert isinstance(result["proposal_tips"], str)
