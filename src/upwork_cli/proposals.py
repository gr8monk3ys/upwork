"""Proposals: the cover letters this tool owns.

A Proposal lives only here -- Upwork's terms forbid submitting one through
their API, so it is always copied out and sent by hand. That makes storage,
not Upwork, its source of truth, and this module the one place that decides
what happens to a Proposal after it is drafted.

Composes ``db`` with the Pipeline the way ``jobs`` composes the client with
``db``. Failures are raised, not printed.
"""

from upwork_cli import pipeline
from upwork_cli.db import get_proposal, mark_proposal_outcome, save_proposal
from upwork_cli.models import OUTCOMES, Proposal

#: The Stage a recorded Outcome moves its Job to. ``no_response`` moves
#: nothing: the freelancer heard nothing back, which is not yet a loss.
OUTCOME_STAGES = {"won": "won", "lost": "lost"}


class ProposalsError(RuntimeError):
    """Raised when a Proposal cannot be stored or its Outcome recorded."""


def record(job_id: str, job_title: str, content: str, tone: str) -> Proposal:
    """Store a freshly drafted Proposal and move its Job to ``drafted``.

    The Job moves on drafting, not on sending: this tool cannot know when a
    Proposal was actually submitted, so ``drafted`` is the furthest the
    Pipeline can honestly place it.
    """
    proposal_id = save_proposal(job_id, job_title, content, tone)
    pipeline.move(job_id, "drafted")
    stored = get_proposal(proposal_id)
    if stored is None:
        raise ProposalsError(f"Proposal #{proposal_id} could not be read back.")
    return stored


def mark(proposal_id: int, outcome: str) -> Proposal:
    """Record what became of a Proposal, moving its Job to match.

    Raises:
        ProposalsError: on an unknown Outcome or an unknown Proposal.
    """
    if outcome not in OUTCOMES:
        raise ProposalsError(
            f"Unknown outcome: {outcome}. Use one of {', '.join(OUTCOMES)}."
        )
    proposal = get_proposal(proposal_id)
    if proposal is None:
        raise ProposalsError(f"Proposal #{proposal_id} not found.")

    mark_proposal_outcome(proposal_id, outcome)
    stage = OUTCOME_STAGES.get(outcome)
    if stage and proposal.job_id:
        pipeline.move(proposal.job_id, stage)

    proposal.outcome = outcome
    return proposal
