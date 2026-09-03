"""Tests for the AI profile audit module upwork_cli.ai.auditor."""

import json
from unittest.mock import patch

import pytest

from tests.conftest import mock_anthropic_response
from upwork_cli.ai.auditor import audit_profile
from upwork_cli.ai.utils import AIError

SAMPLE_AUDIT_JSON = json.dumps(
    {
        "total_score": 72,
        "breakdown": [
            {"area": "Title", "score": 18, "feedback": "Great title."},
            {"area": "Overview", "score": 15, "feedback": "Good but could be longer."},
            {"area": "Skills", "score": 14, "feedback": "Needs more skills."},
            {"area": "Portfolio", "score": 10, "feedback": "Add more items."},
            {
                "area": "Rate & Experience",
                "score": 15,
                "feedback": "Rate is competitive.",
            },
        ],
        "top_3_improvements": [
            "Add 3 more portfolio items.",
            "Expand overview to 500+ characters.",
            "Add 5 more relevant skills.",
        ],
    }
)


class TestAuditProfile:
    def test_happy_path(self):
        resp = mock_anthropic_response(SAMPLE_AUDIT_JSON)
        with patch("upwork_cli.ai.utils.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = resp
            result = audit_profile("profile text", "fake-key")

        assert result["total_score"] == 72
        assert len(result["breakdown"]) == 5
        assert len(result["top_3_improvements"]) == 3

    def test_fenced_json_response(self):
        fenced = f"```json\n{SAMPLE_AUDIT_JSON}\n```"
        resp = mock_anthropic_response(fenced)
        with patch("upwork_cli.ai.utils.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = resp
            result = audit_profile("profile text", "key")

        assert result["total_score"] == 72

    def test_score_clamped_to_100(self):
        bad_json = json.dumps(
            {"total_score": 150, "breakdown": [], "top_3_improvements": []}
        )
        resp = mock_anthropic_response(bad_json)
        with patch("upwork_cli.ai.utils.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = resp
            result = audit_profile("profile text", "key")

        assert result["total_score"] == 100

    def test_api_error_raises(self):
        with patch("upwork_cli.ai.utils.Anthropic") as MockClient:
            MockClient.return_value.messages.create.side_effect = Exception("API down")
            with pytest.raises(AIError):
                audit_profile("profile text", "key")

    def test_unparseable_response_raises(self):
        resp = mock_anthropic_response("definitely not json")
        with patch("upwork_cli.ai.utils.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = resp
            with pytest.raises(AIError, match="Could not parse audit response"):
                audit_profile("profile text", "key")
