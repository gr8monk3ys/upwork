"""Tests for the AI client research module."""

import json
from unittest.mock import patch


from upwork_cli.ai.researcher import research_client
from tests.conftest import mock_anthropic_response


SAMPLE_JSON = json.dumps(
    {
        "risk_level": "low",
        "spending_tier": "large",
        "brief": "Well-established client with strong track record.",
        "proposal_tips": "Emphasize reliability and past results.",
    }
)


class TestResearchClient:
    def test_happy_path(self):
        resp = mock_anthropic_response(SAMPLE_JSON)
        with patch("upwork_cli.ai.researcher.Anthropic") as M:
            M.return_value.messages.create.return_value = resp
            result = research_client("job", 150000, 42, 4.9, "US", True, "key")
        assert result["risk_level"] == "low"
        assert result["spending_tier"] == "large"

    def test_fenced_json(self):
        resp = mock_anthropic_response(f"```json\n{SAMPLE_JSON}\n```")
        with patch("upwork_cli.ai.researcher.Anthropic") as M:
            M.return_value.messages.create.return_value = resp
            result = research_client("job", None, None, None, "", False, "key")
        assert result["risk_level"] == "low"

    def test_fallback_on_error(self):
        with patch("upwork_cli.ai.researcher.Anthropic") as M:
            M.return_value.messages.create.side_effect = Exception("fail")
            result = research_client("job", None, None, None, "", False, "key")
        assert result["risk_level"] == "unknown"

    def test_fallback_on_bad_json(self):
        resp = mock_anthropic_response("not json")
        with patch("upwork_cli.ai.researcher.Anthropic") as M:
            M.return_value.messages.create.return_value = resp
            result = research_client("job", None, None, None, "", False, "key")
        assert result["risk_level"] == "unknown"
