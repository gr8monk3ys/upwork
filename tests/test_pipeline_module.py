"""Tests for ``upwork_cli.pipeline`` and ``upwork_cli.timestamps``.

The win-rate arithmetic lived in a SQL function, the Stage set in `db`, and
the transition rules in three other modules. None of it had a direct test.
"""

from datetime import datetime, timezone

import pytest

from tests.conftest import _make_job_posting
from upwork_cli import pipeline, timestamps
from upwork_cli.db import init_db, upsert_job


@pytest.fixture
def job(isolated_config):
    init_db()
    posting = _make_job_posting()
    upsert_job(posting)
    return posting


class TestMove:
    def test_a_move_is_recorded_and_readable(self, job):
        pipeline.move(job.id, "applied", notes="sent today")
        entries = pipeline.entries()
        assert [(e.job_id, e.stage, e.notes) for e in entries] == [
            (job.id, "applied", "sent today")
        ]

    def test_a_job_occupies_one_stage_at_a_time(self, job):
        pipeline.move(job.id, "found")
        pipeline.move(job.id, "applied")
        assert pipeline.entries("found") == []
        assert [e.job_id for e in pipeline.entries("applied")] == [job.id]

    def test_every_move_is_kept(self, job):
        pipeline.move(job.id, "found")
        pipeline.move(job.id, "applied")
        # Both rows land in the same second, so the DESC ordering ties;
        # what matters is that neither move was dropped.
        moves = {(t.from_stage, t.to_stage) for t in pipeline.history(job.id)}
        assert moves == {(None, "found"), ("found", "applied")}

    def test_an_unknown_stage_raises(self, job):
        """`click.Choice` was the only validation, and three callers bypassed it."""
        with pytest.raises(pipeline.PipelineError, match="Unknown stage"):
            pipeline.move(job.id, "shortlisted")

    def test_filtering_by_an_unknown_stage_raises(self, job):
        with pytest.raises(pipeline.PipelineError, match="Unknown stage"):
            pipeline.entries("shortlisted")


class TestStats:
    def _seed(self, stages: list[str]) -> None:
        for i, stage in enumerate(stages):
            posting = _make_job_posting(id=f"~job{i}")
            upsert_job(posting)
            pipeline.move(posting.id, stage)

    def test_an_empty_pipeline_has_no_win_rate(self, isolated_config):
        init_db()
        assert pipeline.stats().total == 0
        assert pipeline.stats().win_rate == 0.0

    def test_win_rate_counts_only_submitted_jobs(self, isolated_config):
        """A Job still at `found` or `drafted` must not drag the rate down."""
        init_db()
        self._seed(["won", "lost", "found", "drafted"])
        stats = pipeline.stats()
        assert stats.total == 4
        assert stats.submitted == 2
        assert stats.win_rate == 50.0

    def test_interviewing_counts_as_submitted(self, isolated_config):
        init_db()
        self._seed(["won", "interviewing", "applied", "lost"])
        assert pipeline.stats().win_rate == 25.0

    def test_only_unsubmitted_jobs_is_still_zero_not_a_crash(self, isolated_config):
        init_db()
        self._seed(["found", "drafted"])
        assert pipeline.stats().win_rate == 0.0


class TestRecent:
    def test_a_transition_with_an_unreadable_timestamp_is_left_out(self, job):
        pipeline.move(job.id, "found")
        from upwork_cli.db import get_connection

        with get_connection() as conn:
            conn.execute("UPDATE pipeline_history SET moved_at = 'not a date'")
        assert pipeline.recent(days=365) == []


class TestTransitionLabel:
    def test_falls_back_to_the_job_id_when_the_job_is_not_cached(self):
        transition = pipeline.Transition(job_id="~unknown", to_stage="found")
        assert transition.label == "~unknown"


class TestTimestamps:
    @pytest.mark.parametrize(
        "value",
        [
            "2026-03-08T12:00:00Z",
            "2026-03-08T12:00:00+00:00",
            "2026-03-08 12:00:00",
            "2026-03-08T12:00:00",
        ],
    )
    def test_every_shape_this_tool_receives_reads_as_utc_noon(self, value):
        parsed = timestamps.parse(value)
        assert parsed == datetime(2026, 3, 8, 12, 0, tzinfo=timezone.utc)

    def test_rfc_822_from_the_rss_feeds(self):
        parsed = timestamps.parse("Sun, 08 Mar 2026 12:00:00 GMT")
        assert parsed == datetime(2026, 3, 8, 12, 0, tzinfo=timezone.utc)

    def test_a_bare_date(self):
        assert timestamps.parse("2026-03-08") == datetime(
            2026, 3, 8, tzinfo=timezone.utc
        )

    def test_unreadable_values_are_none_not_a_guess(self):
        assert timestamps.parse("") is None
        assert timestamps.parse("not a date") is None


class TestMoveUnknownJob:
    def test_an_uncached_job_is_reported_not_a_traceback(self, isolated_config):
        """Used to surface as a raw sqlite3 FOREIGN KEY traceback."""
        init_db()
        with pytest.raises(pipeline.PipelineError, match="not in the local cache"):
            pipeline.move("~never-seen", "won")
