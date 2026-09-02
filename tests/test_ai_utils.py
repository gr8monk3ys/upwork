"""Tests for the shared AI utility functions."""

from unittest.mock import MagicMock, patch

import anthropic
import pytest

from tests.conftest import mock_anthropic_response
from upwork_cli.ai.utils import (
    DEFAULT_MODEL,
    AIError,
    complete,
    extract_text,
    strip_json_fences,
)


class TestStripJsonFences:
    def test_no_fences(self):
        text = '{"score": 8, "reasoning": "Good match"}'
        assert strip_json_fences(text) == text

    def test_json_fences(self):
        text = '```json\n{"score": 8}\n```'
        assert strip_json_fences(text) == '{"score": 8}'

    def test_plain_fences(self):
        text = '```\n{"key": "value"}\n```'
        assert strip_json_fences(text) == '{"key": "value"}'

    def test_nested_content(self):
        text = '```json\n{"code": "```inner```"}\n```'
        result = strip_json_fences(text)
        assert '"code"' in result

    def test_whitespace_handling(self):
        text = '```json\n  {"score": 5}  \n```'
        result = strip_json_fences(text)
        assert '{"score": 5}' in result

    def test_not_starting_with_fences(self):
        text = 'Some text ```json\n{"a":1}\n```'
        assert strip_json_fences(text) == text


class TestDefaultModel:
    def test_model_is_string(self):
        assert isinstance(DEFAULT_MODEL, str)

    def test_model_contains_claude(self):
        assert "claude" in DEFAULT_MODEL


class TestExtractText:
    def test_text_only(self):
        resp = mock_anthropic_response("hello")
        assert extract_text(resp) == "hello"

    def test_skips_thinking_blocks(self):
        resp = mock_anthropic_response("the answer", include_thinking=True)
        assert extract_text(resp) == "the answer"

    def test_empty_content(self):
        resp = MagicMock()
        resp.content = []
        assert extract_text(resp) == ""


class TestComplete:
    def test_returns_text(self):
        resp = mock_anthropic_response("output text")
        with patch("upwork_cli.ai.utils.Anthropic") as M:
            M.return_value.messages.create.return_value = resp
            assert complete("prompt", "key") == "output text"

    def test_passes_model_override(self):
        resp = mock_anthropic_response("ok")
        with patch("upwork_cli.ai.utils.Anthropic") as M:
            M.return_value.messages.create.return_value = resp
            complete("prompt", "key", model="claude-haiku-4-5")
            kwargs = M.return_value.messages.create.call_args.kwargs
            assert kwargs["model"] == "claude-haiku-4-5"

    def test_defaults_model(self):
        resp = mock_anthropic_response("ok")
        with patch("upwork_cli.ai.utils.Anthropic") as M:
            M.return_value.messages.create.return_value = resp
            complete("prompt", "key")
            kwargs = M.return_value.messages.create.call_args.kwargs
            assert kwargs["model"] == DEFAULT_MODEL

    def test_authentication_error(self):
        with patch("upwork_cli.ai.utils.Anthropic") as M:
            M.return_value.messages.create.side_effect = anthropic.AuthenticationError(
                message="bad key",
                response=MagicMock(status_code=401),
                body={"error": {"message": "bad key"}},
            )
            with pytest.raises(AIError, match="Invalid Anthropic API key"):
                complete("prompt", "bad-key")

    def test_rate_limit_error(self):
        with patch("upwork_cli.ai.utils.Anthropic") as M:
            M.return_value.messages.create.side_effect = anthropic.RateLimitError(
                message="slow down",
                response=MagicMock(status_code=429),
                body={"error": {"message": "slow down"}},
            )
            with pytest.raises(AIError, match="rate limit"):
                complete("prompt", "key")

    def test_generic_error_wrapped(self):
        with patch("upwork_cli.ai.utils.Anthropic") as M:
            M.return_value.messages.create.side_effect = Exception("boom")
            with pytest.raises(AIError, match="Anthropic call failed"):
                complete("prompt", "key")

    def test_no_text_content_raises(self):
        resp = MagicMock()
        resp.content = []
        with patch("upwork_cli.ai.utils.Anthropic") as M:
            M.return_value.messages.create.return_value = resp
            with pytest.raises(AIError, match="no text content"):
                complete("prompt", "key")

    def test_ai_error_is_runtime_error(self):
        assert issubclass(AIError, RuntimeError)
