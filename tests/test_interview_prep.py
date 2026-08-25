"""Tests for the AI interview prep module."""

from unittest.mock import patch

import pytest

from upwork_cli.ai.interview_prep import generate_interview_prep
from tests.conftest import mock_anthropic_response


class TestInterviewPrep:
    def test_happy_path(self):
        resp = mock_anthropic_response("## Likely Questions\n1. Tell me about...")
        with patch("upwork_cli.ai.utils.Anthropic") as M:
            M.return_value.messages.create.return_value = resp
            result = generate_interview_prep("job", "profile", "key")
        assert "Questions" in result

    def test_with_client_research(self):
        resp = mock_anthropic_response("Prep notes with research context.")
        with patch("upwork_cli.ai.utils.Anthropic") as M:
            M.return_value.messages.create.return_value = resp
            result = generate_interview_prep(
                "job", "profile", "key", client_research="Low risk client"
            )
        assert "Prep notes" in result

    def test_raises_on_error(self):
        with patch("upwork_cli.ai.utils.Anthropic") as M:
            M.return_value.messages.create.side_effect = Exception("API down")
            with pytest.raises(RuntimeError, match="Anthropic call failed"):
                generate_interview_prep("job", "profile", "key")
