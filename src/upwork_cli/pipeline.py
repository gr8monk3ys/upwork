"""The Pipeline: where each Job stands, and how it got there.

Every other domain noun got a module in #22-#28; the Pipeline did not, and
the rules for it ended up in four files. The set of Stages lived in ``db``,
the win-rate arithmetic in ``db``, the Stage colours in a command module, and
the transitions themselves in `jobs.py` and two Click callbacks in
`propose.py` -- which passed bare string literals, bypassing the
`click.Choice` that was the only thing validating a Stage anywhere.

A Job occupies exactly one Stage at a time and every move between them is
kept. Failures are raised, not printed.
"""

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from upwork_cli import db, timestamps

#: Every Stage a Job can occupy, in the order it moves through them.
STAGES = ("found", "drafted", "applied", "interviewing", "won", "lost")

#: The Stages that mean a Proposal was actually submitted. The win rate is
#: measured against these, so a Job still at `found` or `drafted` cannot
#: drag it down.
SUBMITTED_STAGES = ("applied", "interviewing", "won", "lost")


class PipelineError(RuntimeError):
    """Raised when a Job cannot be moved to a Stage."""


@dataclass
class PipelineEntry:
    """One Job's position in the Pipeline, with what the listing shows."""

    job_id: str
    stage: str = "found"
    moved_at: str = ""
    notes: str = ""
    title: str = ""
    budget_amount: float | None = None
    budget_currency: str = "USD"
    client_country: str = ""
    category: str = ""
    score: int | None = None

    @classmethod
    def from_db_row(cls, row: Any) -> "PipelineEntry":
        row = dict(row)
        score = row.get("score")
        return cls(
            job_id=row["job_id"],
            stage=row.get("stage") or "found",
            moved_at=row.get("moved_at") or "",
            notes=row.get("notes") or "",
            title=row.get("title") or "",
            budget_amount=row.get("budget_amount"),
            budget_currency=row.get("budget_currency") or "USD",
            client_country=row.get("client_country") or "",
            category=row.get("category") or "",
            score=int(score) if score is not None else None,
        )


@dataclass
class Transition:
    """One recorded move between Stages. ``from_stage`` is None for the first."""

    job_id: str
    to_stage: str
    from_stage: str | None = None
    moved_at: str = ""
    title: str = ""

    @classmethod
    def from_db_row(cls, row: Any) -> "Transition":
        row = dict(row)
        return cls(
            job_id=row.get("job_id") or "",
            to_stage=row.get("to_stage") or "",
            from_stage=row.get("from_stage") or None,
            moved_at=row.get("moved_at") or "",
            title=row.get("title") or "",
        )

    @property
    def label(self) -> str:
        """The Job's title, or its id when the Job is not cached."""
        return self.title or self.job_id


@dataclass
class CategoryCount:
    category: str
    count: int


@dataclass
class PipelineStats:
    """Stage counts and the win rate computed from them."""

    stage_counts: dict[str, int] = field(default_factory=dict)
    top_categories: list[CategoryCount] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(self.stage_counts.values())

    @property
    def submitted(self) -> int:
        """Jobs whose Proposal actually went out."""
        return sum(self.stage_counts.get(stage, 0) for stage in SUBMITTED_STAGES)

    @property
    def win_rate(self) -> float:
        """Won as a percentage of submitted, to one decimal. 0.0 with none."""
        if not self.submitted:
            return 0.0
        return round(self.stage_counts.get("won", 0) / self.submitted * 100, 1)

    def count(self, stage: str) -> int:
        return self.stage_counts.get(stage, 0)


def move(job_id: str, stage: str, notes: str = "") -> None:
    """Move a Job to *stage*, keeping the transition.

    Raises:
        PipelineError: on a Stage that is not one of :data:`STAGES`, or on a
            Job the cache does not hold. The Stage check is the only
            validation there has ever been outside `click.Choice`, which
            three callers bypassed with string literals.
    """
    if stage not in STAGES:
        raise PipelineError(f"Unknown stage: {stage}. Use one of {', '.join(STAGES)}.")
    try:
        db.set_pipeline_stage(job_id, stage, notes)
    except sqlite3.IntegrityError as exc:
        # The pipeline references jobs(id); an unknown job used to surface
        # as a raw FOREIGN KEY traceback.
        raise PipelineError(
            f"Job {job_id} is not in the local cache. "
            "Run 'upwork jobs search' or 'upwork jobs detail' for it first."
        ) from exc


def entries(stage: str | None = None) -> list[PipelineEntry]:
    """Every Job in the Pipeline, most recently moved first."""
    if stage is not None and stage not in STAGES:
        raise PipelineError(f"Unknown stage: {stage}. Use one of {', '.join(STAGES)}.")
    return [PipelineEntry.from_db_row(r) for r in db.get_pipeline_jobs(stage=stage)]


def stats() -> PipelineStats:
    """Stage counts and top categories for the whole Pipeline."""
    raw = db.get_pipeline_stats()
    return PipelineStats(
        stage_counts=raw["stage_counts"],
        top_categories=[
            CategoryCount(category=c["category"], count=c["count"])
            for c in raw["top_categories"]
        ],
    )


def history(job_id: str | None = None) -> list[Transition]:
    """Recorded transitions, most recent first."""
    return [Transition.from_db_row(r) for r in db.get_pipeline_history(job_id)]


def recent(days: int, now: datetime | None = None) -> list[Transition]:
    """Transitions inside the last *days*, most recent first.

    A transition whose timestamp cannot be read is left out rather than
    guessed at.
    """
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=days)
    found = []
    for transition in history():
        moved_at = timestamps.parse(transition.moved_at)
        if moved_at is not None and moved_at >= cutoff:
            found.append(transition)
    return found
