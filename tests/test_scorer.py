"""Tests for the AI job scoring module upwork_cli.ai.scorer."""

from unittest.mock import patch


from upwork_cli.ai.scorer import score_job, score_jobs_batch
from tests.conftest import mock_anthropic_response


class TestScoreJob:
    def test_clean_json_response(self):
        resp = mock_anthropic_response('{"score": 8, "reasoning": "Great match."}')
        with patch("upwork_cli.ai.scorer.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = resp
            score, reasoning = score_job("job text", "profile text", "fake-key")

        assert score == 8
        assert reasoning == "Great match."

    def test_fenced_json_response(self):
        resp = mock_anthropic_response(
            '```json\n{"score": 7, "reasoning": "OK match."}\n```'
        )
        with patch("upwork_cli.ai.scorer.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = resp
            score, reasoning = score_job("job", "profile", "key")

        assert score == 7
        assert reasoning == "OK match."

    def test_score_clamped_above_10(self):
        resp = mock_anthropic_response('{"score": 15, "reasoning": "Over max."}')
        with patch("upwork_cli.ai.scorer.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = resp
            score, _ = score_job("job", "profile", "key")

        assert score == 10

    def test_score_clamped_below_1(self):
        resp = mock_anthropic_response('{"score": -3, "reasoning": "Under min."}')
        with patch("upwork_cli.ai.scorer.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = resp
            score, _ = score_job("job", "profile", "key")

        assert score == 1

    def test_invalid_json_fallback(self):
        resp = mock_anthropic_response("This is not JSON at all.")
        with patch("upwork_cli.ai.scorer.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = resp
            score, reasoning = score_job("job", "profile", "key")

        assert score == 0
        assert "Scoring failed" in reasoning

    def test_api_exception_handling(self):
        with patch("upwork_cli.ai.scorer.Anthropic") as MockClient:
            MockClient.return_value.messages.create.side_effect = Exception("API down")
            score, reasoning = score_job("job", "profile", "key")

        assert score == 0
        assert "Scoring failed" in reasoning


class TestScoreJobsBatch:
    def test_batch_sort_order(self):
        responses = [
            mock_anthropic_response('{"score": 3, "reasoning": "Low."}'),
            mock_anthropic_response('{"score": 9, "reasoning": "High."}'),
            mock_anthropic_response('{"score": 6, "reasoning": "Mid."}'),
        ]
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            resp = responses[call_count]
            call_count += 1
            return resp

        with patch("upwork_cli.ai.scorer.Anthropic") as MockClient:
            MockClient.return_value.messages.create.side_effect = side_effect
            jobs = [
                {"id": "a", "title": "Job A", "summary": "..."},
                {"id": "b", "title": "Job B", "summary": "..."},
                {"id": "c", "title": "Job C", "summary": "..."},
            ]
            result = score_jobs_batch(jobs, "profile", "key")

        scores = [r["score"] for r in result]
        assert scores == [9, 6, 3]
