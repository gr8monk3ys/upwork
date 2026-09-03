"""Tests for the AI proposal learning module."""

from unittest.mock import patch

import pytest

from tests.conftest import mock_anthropic_response
from upwork_cli.ai.learner import extract_winning_patterns


class TestExtractWinningPatterns:
    def test_happy_path(self):
        resp = mock_anthropic_response("## Opening Patterns\nStart with a hook...")
        with patch("upwork_cli.ai.utils.Anthropic") as M:
            M.return_value.messages.create.return_value = resp
            result = extract_winning_patterns(
                [
                    {
                        "content": "My winning proposal",
                        "job_title": "Dev",
                        "tone": "professional",
                    }
                ],
                "key",
            )
        assert "Opening" in result

    def test_empty_proposals_raises(self):
        with pytest.raises(RuntimeError, match="No winning proposals"):
            extract_winning_patterns([], "key")

    def test_api_error_raises(self):
        with patch("upwork_cli.ai.utils.Anthropic") as M:
            M.return_value.messages.create.side_effect = Exception("fail")
            with pytest.raises(RuntimeError, match="Anthropic call failed"):
                extract_winning_patterns(
                    [{"content": "text", "job_title": "J", "tone": "casual"}],
                    "key",
                )

    def test_multiple_proposals(self):
        resp = mock_anthropic_response("Style guide from multiple proposals.")
        with patch("upwork_cli.ai.utils.Anthropic") as M:
            M.return_value.messages.create.return_value = resp
            proposals = [
                {
                    "content": f"Proposal {i}",
                    "job_title": f"Job {i}",
                    "tone": "professional",
                }
                for i in range(3)
            ]
            result = extract_winning_patterns(proposals, "key")
        assert "Style guide" in result
