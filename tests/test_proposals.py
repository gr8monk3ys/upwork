"""Tests for ``upwork_cli.proposals`` and the Proposal type.

The Proposal is the one noun this tool owns outright, and until now it had no
type: `db` handed back sqlite rows and five call sites re-derived the column
names and their defaults, two of them disagreeing about what the default was.
"""

import pytest

from upwork_cli import proposals
from upwork_cli.db import get_pipeline_jobs, get_proposal, init_db, save_proposal
from upwork_cli.models import Proposal


def _stage_of(job_id: str) -> str | None:
    return {r["job_id"]: r["stage"] for r in get_pipeline_jobs()}.get(job_id)


class TestProposalType:
    def test_from_db_row_needs_only_an_id(self):
        proposal = Proposal.from_db_row({"id": 7})
        assert proposal.id == 7
        assert proposal.tone == "professional"
        assert proposal.outcome is None

    def test_title_falls_back_once_for_every_caller(self):
        assert Proposal(id=1, job_title="").title == "Untitled"
        assert Proposal(id=1, job_title="Build an API").title == "Build an API"

    def test_an_unrecorded_outcome_is_none_not_a_loss(self):
        assert Proposal.from_db_row({"id": 1, "outcome": ""}).outcome is None
        assert Proposal(id=1).is_won is False


class TestRecord:
    def test_storing_a_draft_moves_the_job_to_drafted(self, isolated_config):
        init_db()
        stored = proposals.record("~job", "Build an API", "Dear client", "casual")
        assert stored.id > 0
        assert stored.content == "Dear client"
        assert stored.tone == "casual"
        assert _stage_of("~job") == "drafted"

    def test_the_stored_proposal_reads_back_identically(self, isolated_config):
        init_db()
        stored = proposals.record("~job", "Title", "Body", "technical")
        assert get_proposal(stored.id) == stored


class TestMark:
    def test_won_moves_the_job_to_won(self, isolated_config):
        init_db()
        stored = proposals.record("~job", "Title", "Body", "professional")
        marked = proposals.mark(stored.id, "won")
        assert marked.outcome == "won"
        assert marked.is_won
        assert _stage_of("~job") == "won"

    def test_lost_moves_the_job_to_lost(self, isolated_config):
        init_db()
        stored = proposals.record("~job", "Title", "Body", "professional")
        proposals.mark(stored.id, "lost")
        assert _stage_of("~job") == "lost"

    def test_no_response_records_the_outcome_but_moves_nothing(self, isolated_config):
        """Hearing nothing back is not yet a loss."""
        init_db()
        stored = proposals.record("~job", "Title", "Body", "professional")
        proposals.mark(stored.id, "no_response")
        assert get_proposal(stored.id).outcome == "no_response"
        assert _stage_of("~job") == "drafted"

    def test_unknown_outcome_raises(self, isolated_config):
        init_db()
        stored = proposals.record("~job", "Title", "Body", "professional")
        with pytest.raises(proposals.ProposalsError, match="Unknown outcome"):
            proposals.mark(stored.id, "maybe")

    def test_unknown_proposal_raises(self, isolated_config):
        init_db()
        with pytest.raises(proposals.ProposalsError, match="not found"):
            proposals.mark(999, "won")

    def test_a_proposal_with_no_job_still_records(self, isolated_config):
        init_db()
        proposal_id = save_proposal("", "", "Body", "professional")
        assert proposals.mark(proposal_id, "won").outcome == "won"
