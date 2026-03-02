"""Tests for the shared AI utility functions."""

from upwork_cli.ai.utils import DEFAULT_MODEL, strip_json_fences


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
