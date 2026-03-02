"""Tests for the job pipeline dashboard (DB operations and CLI)."""

import pytest
from click.testing import CliRunner

from upwork_cli.cli import cli
from upwork_cli.db import (
    init_db,
    upsert_job,
    set_pipeline_stage,
    set_pipeline_stage_if_not_exists,
    get_pipeline_jobs,
    get_pipeline_stats,
    get_pipeline_history,
    mark_proposal_outcome,
    get_winning_proposals,
    save_proposal,
    PIPELINE_STAGES,
)
from tests.conftest import _make_job_dict


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def seeded_db(isolated_config):
    """Init DB and insert a sample job."""
    init_db()
    job = _make_job_dict()
    upsert_job(job)
    return job


class TestPipelineDb:
    def test_set_and_get_stage(self, seeded_db):
        job = seeded_db
        set_pipeline_stage(job["id"], "found")
        jobs = get_pipeline_jobs(stage="found")
        assert len(jobs) == 1
        assert jobs[0]["job_id"] == job["id"]

    def test_move_between_stages(self, seeded_db):
        job = seeded_db
        set_pipeline_stage(job["id"], "found")
        set_pipeline_stage(job["id"], "applied")

        # Should only be in "applied" now
        assert len(get_pipeline_jobs(stage="found")) == 0
        assert len(get_pipeline_jobs(stage="applied")) == 1

    def test_history_tracked(self, seeded_db):
        job = seeded_db
        set_pipeline_stage(job["id"], "found")
        set_pipeline_stage(job["id"], "applied")
        set_pipeline_stage(job["id"], "interviewing")

        history = get_pipeline_history(job["id"])
        assert len(history) == 3
        # Verify all transitions recorded (order may vary with same-second timestamps)
        transitions = [(h["from_stage"], h["to_stage"]) for h in history]
        assert (None, "found") in transitions
        assert ("found", "applied") in transitions
        assert ("applied", "interviewing") in transitions

    def test_set_if_not_exists_no_overwrite(self, seeded_db):
        job = seeded_db
        set_pipeline_stage(job["id"], "applied")
        set_pipeline_stage_if_not_exists(job["id"], "found")

        # Should still be "applied"
        jobs = get_pipeline_jobs(stage="applied")
        assert len(jobs) == 1

    def test_stats_counts(self, isolated_config):
        init_db()
        for i, stage in enumerate(["found", "found", "applied", "won"]):
            job = _make_job_dict(id=f"~0{i}")
            upsert_job(job)
            set_pipeline_stage(job["id"], stage)

        stats = get_pipeline_stats()
        assert stats["stage_counts"]["found"] == 2
        assert stats["stage_counts"]["applied"] == 1
        assert stats["stage_counts"]["won"] == 1
        assert stats["total"] == 4
        assert stats["win_rate"] == 50.0  # 1 won / (1 applied + 1 won) = 50%

    def test_get_all_pipeline_jobs(self, seeded_db):
        job = seeded_db
        set_pipeline_stage(job["id"], "found")
        all_jobs = get_pipeline_jobs()
        assert len(all_jobs) == 1

    def test_pipeline_stages_constant(self):
        assert "found" in PIPELINE_STAGES
        assert "won" in PIPELINE_STAGES
        assert "lost" in PIPELINE_STAGES


class TestProposalOutcome:
    def test_mark_and_get_winning(self, isolated_config):
        init_db()
        pid = save_proposal("~01abc", "Test Job", "My proposal.", "professional")
        mark_proposal_outcome(pid, "won")
        winners = get_winning_proposals()
        assert len(winners) == 1
        assert winners[0]["outcome"] == "won"


class TestPipelineCli:
    def test_view_empty(self, runner, isolated_config):
        init_db()
        result = runner.invoke(cli, ["pipeline", "view"])
        assert result.exit_code == 0
        assert "No jobs" in result.output

    def test_move_and_view(self, runner, isolated_config):
        init_db()
        job = _make_job_dict()
        upsert_job(job)
        result = runner.invoke(cli, ["pipeline", "move", job["id"], "found"])
        assert result.exit_code == 0
        assert "moved to" in result.output

    def test_stats_empty(self, runner, isolated_config):
        init_db()
        result = runner.invoke(cli, ["pipeline", "stats"])
        assert result.exit_code == 0
        assert "No jobs" in result.output
