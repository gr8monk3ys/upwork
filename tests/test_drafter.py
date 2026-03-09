"""Tests for the AI proposal drafting module upwork_cli.ai.drafter."""

from unittest.mock import patch, MagicMock

import pytest
import anthropic

from upwork_cli.ai.drafter import draft_proposal, refine_proposal
from tests.conftest import mock_anthropic_response


class TestDraftProposal:
    def test_happy_path(self):
        resp = mock_anthropic_response("Here is your tailored proposal.")
        with patch("upwork_cli.ai.drafter.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = resp
            result = draft_proposal("job summary", "profile", "fake-key")

        assert result == "Here is your tailored proposal."

    def test_invalid_tone_raises(self):
        with pytest.raises(ValueError, match="Invalid tone"):
            draft_proposal("job", "profile", "key", tone="angry")

    def test_invalid_length_raises(self):
        with pytest.raises(ValueError, match="Invalid length"):
            draft_proposal("job", "profile", "key", length="huge")

    def test_authentication_error(self):
        with patch("upwork_cli.ai.drafter.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.side_effect = (
                anthropic.AuthenticationError(
                    message="Invalid API key",
                    response=MagicMock(status_code=401),
                    body={"error": {"message": "Invalid API key"}},
                )
            )
            with pytest.raises(RuntimeError, match="Invalid Anthropic API key"):
                draft_proposal("job", "profile", "bad-key")

    def test_rate_limit_error(self):
        with patch("upwork_cli.ai.drafter.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.side_effect = (
                anthropic.RateLimitError(
                    message="Rate limited",
                    response=MagicMock(status_code=429),
                    body={"error": {"message": "Rate limited"}},
                )
            )
            with pytest.raises(RuntimeError, match="rate limit"):
                draft_proposal("job", "profile", "key")

    def test_generic_api_error(self):
        with patch("upwork_cli.ai.drafter.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.side_effect = anthropic.APIError(
                message="Server error",
                request=MagicMock(),
                body={"error": {"message": "Server error"}},
            )
            with pytest.raises(RuntimeError, match="Anthropic API error"):
                draft_proposal("job", "profile", "key")


class TestRefineProposal:
    def test_refine_returns_text(self):
        resp = mock_anthropic_response("Refined proposal text.")
        with patch("upwork_cli.ai.drafter.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = resp
            result = refine_proposal("draft", "make it shorter", "key")

        assert result == "Refined proposal text."
