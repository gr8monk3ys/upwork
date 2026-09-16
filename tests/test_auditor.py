"""Tests for the AI profile audit module upwork_cli.ai.auditor."""

import json

import pytest

from tests.fakes import FakeCompleter
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
    def test_happy_path(self, use_completer):
        use_completer(FakeCompleter(SAMPLE_AUDIT_JSON))
        result = audit_profile("profile text", "fake-key")
        assert result["total_score"] == 72
        assert len(result["breakdown"]) == 5
        assert len(result["top_3_improvements"]) == 3

    def test_fenced_json_response(self, use_completer):
        use_completer(FakeCompleter(f"```json\n{SAMPLE_AUDIT_JSON}\n```"))
        assert audit_profile("profile text", "key")["total_score"] == 72

    def test_the_profile_reaches_the_model(self, use_completer):
        fake = use_completer(FakeCompleter(SAMPLE_AUDIT_JSON))
        audit_profile("Senior Python engineer, 8 years", "key")
        assert "Senior Python engineer, 8 years" in fake.prompt

    def test_score_clamped_to_100(self, use_completer):
        use_completer(
            FakeCompleter(
                json.dumps(
                    {"total_score": 150, "breakdown": [], "top_3_improvements": []}
                )
            )
        )
        assert audit_profile("profile text", "key")["total_score"] == 100

    def test_api_error_raises(self, use_completer):
        use_completer(FakeCompleter(error=AIError("Anthropic call failed: API down")))
        with pytest.raises(AIError):
            audit_profile("profile text", "key")

    def test_unparseable_response_raises(self, use_completer):
        use_completer(FakeCompleter("definitely not json"))
        with pytest.raises(AIError, match="Could not parse audit response"):
            audit_profile("profile text", "key")
