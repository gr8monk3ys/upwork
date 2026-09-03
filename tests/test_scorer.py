"""Tests for the AI job scoring module upwork_cli.ai.scorer."""

from unittest.mock import patch

import pytest

from tests.conftest import mock_anthropic_response
from upwork_cli.ai.scorer import score_job, score_jobs_batch
from upwork_cli.ai.utils import AIError


class TestScoreJob:
    def test_clean_json_response(self):
        resp = mock_anthropic_response('{"score": 8, "reasoning": "Great match."}')
        with patch("upwork_cli.ai.utils.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = resp
            score, reasoning = score_job("job text", "profile text", "fake-key")

        assert score == 8
        assert reasoning == "Great match."

    def test_fenced_json_response(self):
        resp = mock_anthropic_response(
            '```json\n{"score": 7, "reasoning": "OK match."}\n```'
        )
        with patch("upwork_cli.ai.utils.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = resp
            score, reasoning = score_job("job", "profile", "key")

        assert score == 7
        assert reasoning == "OK match."

    def test_thinking_blocks_skipped(self):
        resp = mock_anthropic_response(
            '{"score": 9, "reasoning": "Strong."}', include_thinking=True
        )
        with patch("upwork_cli.ai.utils.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = resp
            score, _ = score_job("job", "profile", "key")

        assert score == 9

    def test_score_clamped_above_10(self):
        resp = mock_anthropic_response('{"score": 15, "reasoning": "Over max."}')
        with patch("upwork_cli.ai.utils.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = resp
            score, _ = score_job("job", "profile", "key")

        assert score == 10

    def test_score_clamped_below_1(self):
        resp = mock_anthropic_response('{"score": -3, "reasoning": "Under min."}')
        with patch("upwork_cli.ai.utils.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = resp
            score, _ = score_job("job", "profile", "key")

        assert score == 1

    def test_invalid_json_raises(self):
        resp = mock_anthropic_response("This is not JSON at all.")
        with patch("upwork_cli.ai.utils.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = resp
            with pytest.raises(AIError, match="Could not parse scoring response"):
                score_job("job", "profile", "key")

    def test_api_exception_raises(self):
        with patch("upwork_cli.ai.utils.Anthropic") as MockClient:
            MockClient.return_value.messages.create.side_effect = Exception("API down")
            with pytest.raises(AIError):
                score_job("job", "profile", "key")


class TestScoreJobsBatch:
    def test_batch_sort_order(self):
        responses = {
            "Job A": mock_anthropic_response('{"score": 3, "reasoning": "Low."}'),
            "Job B": mock_anthropic_response('{"score": 9, "reasoning": "High."}'),
            "Job C": mock_anthropic_response('{"score": 6, "reasoning": "Mid."}'),
        }

        def side_effect(**kwargs):
            prompt = kwargs["messages"][0]["content"]
            for title, resp in responses.items():
                if title in prompt:
                    return resp
            raise AssertionError("unexpected prompt")

        with patch("upwork_cli.ai.utils.Anthropic") as MockClient:
            MockClient.return_value.messages.create.side_effect = side_effect
            jobs = [
                {"id": "a", "title": "Job A", "summary": "about Job A"},
                {"id": "b", "title": "Job B", "summary": "about Job B"},
                {"id": "c", "title": "Job C", "summary": "about Job C"},
            ]
            result = score_jobs_batch(jobs, "profile", "key")

        scores = [r["score"] for r in result]
        assert scores == [9, 6, 3]

    def test_failed_jobs_marked_none_and_sorted_last(self):
        def side_effect(**kwargs):
            prompt = kwargs["messages"][0]["content"]
            if "about Job B" in prompt:
                raise RuntimeError("API down")
            return mock_anthropic_response('{"score": 7, "reasoning": "Fine."}')

        with patch("upwork_cli.ai.utils.Anthropic") as MockClient:
            MockClient.return_value.messages.create.side_effect = side_effect
            jobs = [
                {"id": "a", "title": "Job A", "summary": "about Job A"},
                {"id": "b", "title": "Job B", "summary": "about Job B"},
            ]
            result = score_jobs_batch(jobs, "profile", "key")

        assert result[0]["id"] == "a"
        assert result[0]["score"] == 7
        assert result[1]["id"] == "b"
        assert result[1]["score"] is None
        assert "error" in result[1]

    def test_sequential_workers(self):
        resp = mock_anthropic_response('{"score": 5, "reasoning": "OK."}')
        with patch("upwork_cli.ai.utils.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = resp
            result = score_jobs_batch(
                [{"id": "a", "title": "A", "summary": "s"}],
                "profile",
                "key",
                max_workers=1,
            )
        assert result[0]["score"] == 5
