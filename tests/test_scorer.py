"""Tests for the AI job scoring module upwork_cli.ai.scorer."""

import pytest

from tests.fakes import FakeCompleter
from upwork_cli.ai.scorer import score_job, score_jobs_batch
from upwork_cli.ai.utils import AIError


class TestScoreJob:
    def test_clean_json_response(self, use_completer):
        use_completer(FakeCompleter('{"score": 8, "reasoning": "Great match."}'))
        assert score_job("job text", "profile text", "fake-key") == (
            8,
            "Great match.",
        )

    def test_fenced_json_response(self, use_completer):
        use_completer(
            FakeCompleter('```json\n{"score": 7, "reasoning": "OK match."}\n```')
        )
        assert score_job("job", "profile", "key") == (7, "OK match.")

    def test_score_clamped_above_10(self, use_completer):
        use_completer(FakeCompleter('{"score": 15, "reasoning": "Over max."}'))
        assert score_job("job", "profile", "key")[0] == 10

    def test_score_clamped_below_1(self, use_completer):
        use_completer(FakeCompleter('{"score": -3, "reasoning": "Under min."}'))
        assert score_job("job", "profile", "key")[0] == 1

    def test_invalid_json_raises(self, use_completer):
        use_completer(FakeCompleter("This is not JSON at all."))
        with pytest.raises(AIError, match="Could not parse scoring response"):
            score_job("job", "profile", "key")

    def test_api_exception_raises(self, use_completer):
        use_completer(FakeCompleter(error=AIError("Anthropic call failed: API down")))
        with pytest.raises(AIError):
            score_job("job", "profile", "key")


class TestScoreJobsBatch:
    def test_batch_sort_order(self, use_completer):
        answers = {
            "Job A": '{"score": 3, "reasoning": "Low."}',
            "Job B": '{"score": 9, "reasoning": "High."}',
            "Job C": '{"score": 6, "reasoning": "Mid."}',
        }

        def responder(prompt: str) -> str:
            for title, answer in answers.items():
                if title in prompt:
                    return answer
            raise AssertionError("unexpected prompt")

        use_completer(FakeCompleter(responder=responder))
        jobs = [
            {"id": "a", "title": "Job A", "summary": "about Job A"},
            {"id": "b", "title": "Job B", "summary": "about Job B"},
            {"id": "c", "title": "Job C", "summary": "about Job C"},
        ]
        assert [r["score"] for r in score_jobs_batch(jobs, "profile", "key")] == [
            9,
            6,
            3,
        ]

    def test_failed_jobs_marked_none_and_sorted_last(self, use_completer):
        def responder(prompt: str) -> str:
            if "about Job B" in prompt:
                raise AIError("API down")
            return '{"score": 7, "reasoning": "Fine."}'

        use_completer(FakeCompleter(responder=responder))
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

    def test_sequential_workers(self, use_completer):
        use_completer(FakeCompleter('{"score": 5, "reasoning": "OK."}'))
        result = score_jobs_batch(
            [{"id": "a", "title": "A", "summary": "s"}],
            "profile",
            "key",
            max_workers=1,
        )
        assert result[0]["score"] == 5
