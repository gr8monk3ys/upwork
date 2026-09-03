"""Data models for Upwork API responses."""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


def _to_float(value: Any, default: float | None = 0.0) -> float | None:
    """Coerce an API value to a float, falling back rather than raising."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


@dataclass
class JobPosting:
    id: str
    title: str
    description: str = ""
    skills: list[str] = field(default_factory=list)
    budget_amount: float | None = None
    budget_currency: str = "USD"
    duration: str = ""
    duration_label: str = ""
    engagement: str = ""
    created_at: str = ""
    client_country: str = ""
    client_total_spent: float | None = None
    client_total_hires: int | None = None
    client_feedback: float | None = None
    client_verified: bool = False
    category: str = ""
    subcategory: str = ""

    @classmethod
    def from_graphql(cls, node: dict[str, Any]) -> "JobPosting":
        client = node.get("client") or {}
        amount = node.get("amount") or {}
        total_spent = client.get("totalSpent") or {}
        occupations = node.get("occupations") or {}
        cat = occupations.get("category") or {}
        subcat = occupations.get("subcategory") or {}

        return cls(
            id=node.get("id") or node.get("ciphertext", ""),
            title=node.get("title", ""),
            description=node.get("description", ""),
            skills=[
                s.get("prettyName") or s.get("name", "")
                for s in (node.get("skills") or [])
            ],
            budget_amount=float(amount["amount"]) if amount.get("amount") else None,
            budget_currency=amount.get("currencyCode", "USD"),
            duration=node.get("duration", ""),
            duration_label=node.get("durationLabel", ""),
            engagement=node.get("engagement", ""),
            created_at=node.get("createdDateTime", ""),
            client_country=(client.get("location") or {}).get("country", ""),
            client_total_spent=float(total_spent["amount"])
            if total_spent.get("amount")
            else None,
            client_total_hires=client.get("totalHires"),
            client_feedback=client.get("totalFeedback"),
            client_verified=client.get("verificationStatus") == "VERIFIED",
            category=cat.get("prefLabel", ""),
            subcategory=subcat.get("prefLabel", ""),
        )

    @classmethod
    def from_rest(cls, data: dict[str, Any]) -> "JobPosting":
        budget = data.get("budget") or data.get("amount") or {}
        client = data.get("client") or data.get("buyer") or {}

        return cls(
            id=data.get("id") or data.get("ciphertext", ""),
            title=data.get("title", ""),
            description=data.get("snippet") or data.get("description", ""),
            skills=[
                s if isinstance(s, str) else s.get("name", "")
                for s in (data.get("skills") or [])
            ],
            budget_amount=float(budget["amount"]) if budget.get("amount") else None,
            budget_currency=budget.get("currencyCode", "USD"),
            duration=data.get("duration", ""),
            engagement=data.get("engagement", ""),
            created_at=data.get("date_created", ""),
            client_country=client.get("country", ""),
            client_total_spent=client.get("total_charge"),
            client_total_hires=client.get("total_hires"),
            client_feedback=client.get("feedback"),
        )

    @classmethod
    def from_rss(cls, entry: dict[str, Any]) -> "JobPosting":
        description = entry.get("summary", "")
        budget_str = ""

        if "<b>Budget</b>:" in description:
            parts = description.split("<b>Budget</b>:")
            if len(parts) > 1:
                budget_str = (
                    parts[1].split("<br")[0].strip().replace("$", "").replace(",", "")
                )

        return cls(
            id=entry.get("link", "").split("~")[-1]
            if "~" in entry.get("link", "")
            else entry.get("id", ""),
            title=entry.get("title", ""),
            description=description,
            budget_amount=float(budget_str)
            if budget_str and budget_str.replace(".", "").isdigit()
            else None,
            created_at=entry.get("published", ""),
        )

    @classmethod
    def from_db_row(cls, row: Mapping[str, Any]) -> "JobPosting":
        """Rebuild a posting from a ``jobs`` row.

        The counterpart to :meth:`to_db_dict`. Lenient by design: only ``id``
        is required, every other column falls back to its default, because
        ``MIGRATIONS`` adds columns to databases that already exist and
        ``_run_migrations`` does not fail loudly when one does not apply.

        ``skills`` is stored as JSON text and comes back as a list.

        Accepts a plain mapping or a ``sqlite3.Row``, which supports indexing
        but not ``.get()``.
        """
        row = dict(row)
        skills = row.get("skills") or []
        if isinstance(skills, str):
            try:
                skills = json.loads(skills)
            except (json.JSONDecodeError, TypeError):
                skills = []

        return cls(
            id=row["id"],
            title=row.get("title") or "",
            description=row.get("description") or "",
            skills=list(skills),
            budget_amount=row.get("budget_amount"),
            budget_currency=row.get("budget_currency") or "USD",
            duration=row.get("duration") or "",
            duration_label=row.get("duration_label") or "",
            engagement=row.get("engagement") or "",
            created_at=row.get("created_at") or "",
            client_country=row.get("client_country") or "",
            client_total_spent=row.get("client_total_spent"),
            client_total_hires=row.get("client_total_hires"),
            client_feedback=row.get("client_feedback"),
            client_verified=bool(row.get("client_verified")),
            category=row.get("category") or "",
            subcategory=row.get("subcategory") or "",
        )

    def to_db_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "skills": self.skills,
            "budget_amount": self.budget_amount,
            "budget_currency": self.budget_currency,
            "duration": self.duration,
            "duration_label": self.duration_label,
            "engagement": self.engagement,
            "client_country": self.client_country,
            "client_total_spent": self.client_total_spent,
            "client_total_hires": self.client_total_hires,
            "client_feedback": self.client_feedback,
            "client_verified": self.client_verified,
            "created_at": self.created_at,
            "category": self.category,
            "subcategory": self.subcategory,
        }

    def summary_for_ai(self) -> str:
        parts = [f"Title: {self.title}"]
        if self.description:
            parts.append(f"Description: {self.description[:1000]}")
        if self.skills:
            parts.append(f"Skills: {', '.join(self.skills)}")
        if self.budget_amount:
            parts.append(f"Budget: ${self.budget_amount:,.0f} {self.budget_currency}")
        duration = self.duration_label or self.duration
        if duration:
            parts.append(f"Duration: {duration}")
        if self.engagement:
            parts.append(f"Engagement: {self.engagement}")
        if self.client_country:
            parts.append(f"Client Country: {self.client_country}")
        if self.client_total_spent:
            parts.append(f"Client Total Spent: ${self.client_total_spent:,.0f}")
        if self.client_total_hires:
            parts.append(f"Client Total Hires: {self.client_total_hires}")
        if self.client_feedback:
            parts.append(f"Client Feedback: {self.client_feedback}")
        if self.client_verified:
            parts.append("Client: Payment Verified")
        return "\n".join(parts)


@dataclass
class ScoreResult:
    """The outcome of one attempt to score a Job against the Profile.

    ``score`` is None when the attempt failed and ``error`` says why. A
    failed attempt is never persisted, so a transient API failure cannot
    permanently bury a job.
    """

    job: JobPosting
    score: int | None = None
    reasoning: str = ""
    error: str = ""


@dataclass
class OfferTerms:
    """What an offer pays: a fixed budget, or an hourly rate and cap.

    Carries the number and its currency rather than a formatted string, so
    rendering stays with the caller.
    """

    amount: float | None = None
    currency: str = "USD"
    weekly_hours_limit: int | None = None
    is_fixed: bool = False
    start_date: str = ""
    end_date: str = ""

    @classmethod
    def from_api(cls, terms: dict[str, Any] | None) -> "OfferTerms":
        terms = terms or {}
        dates = {
            "start_date": str(terms.get("expectedStartDate", "") or ""),
            "end_date": str(terms.get("expectedEndDate", "") or ""),
        }
        fixed = terms.get("fixedPriceTerm") or {}
        budget = fixed.get("budget") or {}
        if budget.get("amount") not in (None, ""):
            return cls(
                amount=_to_float(budget.get("amount"), None),
                currency=budget.get("currencyCode", "USD"),
                is_fixed=True,
                **dates,
            )

        hourly = terms.get("hourlyTerms") or {}
        rate = hourly.get("rate") or {}
        if rate.get("amount") not in (None, ""):
            limit = hourly.get("weeklyHoursLimit")
            return cls(
                amount=_to_float(rate.get("amount"), None),
                currency=rate.get("currencyCode", "USD"),
                weekly_hours_limit=int(limit) if str(limit).isdigit() else None,
                **dates,
            )
        return cls(**dates)


@dataclass
class Offer:
    """A contract offer extended by a client, owned by Upwork."""

    id: str
    title: str = ""
    state: str = ""
    kind: str = ""
    client_name: str = ""
    job_title: str = ""
    updated_at: str = ""
    application_id: str = ""
    application_status: str = ""
    description: str = ""
    message_to_contractor: str = ""
    close_job_on_accept: bool = False
    terms: OfferTerms = field(default_factory=OfferTerms)

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Offer":
        data = data or {}
        # A connection node wraps the offer one level down.
        inner = data.get("offer") or {}
        offer_id = str(inner.get("id") or data.get("id", "") or "")

        company = data.get("company") or {}
        client = data.get("client") or {}
        proposal = data.get("vendorProposal") or {}

        return cls(
            id=offer_id,
            title=str(data.get("title", "") or ""),
            state=str(data.get("state", "") or ""),
            kind=str(data.get("type", "") or ""),
            client_name=str(company.get("name") or client.get("name") or ""),
            job_title=str((data.get("job") or {}).get("title", "") or ""),
            updated_at=str(
                data.get("lastUpdatedDateTime")
                or data.get("lastPublishedDateTime")
                or ""
            ),
            application_id=str(proposal.get("id", "") or ""),
            application_status=str(
                (proposal.get("status") or {}).get("status", "") or ""
            ),
            description=str(data.get("description", "") or ""),
            message_to_contractor=str(data.get("messageToContractor", "") or ""),
            close_job_on_accept=bool(data.get("closeJobPostingOnAccept", False)),
            terms=OfferTerms.from_api(data.get("offerTerms")),
        )


@dataclass
class Application:
    """A proposal already submitted on Upwork, read back from its API.

    Not to be confused with a locally drafted Proposal, which Upwork's terms
    forbid submitting through the API.
    """

    id: str
    status: str = ""
    cover_letter: str = ""
    created_at: str = ""
    modified_at: str = ""
    status_changed_at: str = ""
    job: "JobPosting | None" = None

    @classmethod
    def from_api(cls, node: dict[str, Any]) -> "Application":
        node = node or {}
        audit = node.get("auditDetails") or {}
        posting = node.get("marketplaceJobPosting")
        return cls(
            id=str(node.get("id", "") or ""),
            status=str((node.get("status") or {}).get("status", "") or ""),
            cover_letter=str(
                node.get("proposalCoverLetter") or node.get("coverLetter") or ""
            ),
            created_at=str(audit.get("createdDateTime", "") or ""),
            modified_at=str(audit.get("modifiedDateTime", "") or ""),
            status_changed_at=str(audit.get("statusChangedDateTime", "") or ""),
            job=JobPosting.from_graphql(posting) if posting else None,
        )

    @property
    def job_title(self) -> str:
        return self.job.title if self.job else ""

    def sort_key(self, preferred: str = "modified") -> str:
        """The audit timestamp this listing should be ordered by."""
        if preferred == "created":
            return self.created_at
        if preferred == "status":
            return self.status_changed_at or self.modified_at
        return self.modified_at or self.created_at


@dataclass
class Contract:
    id: str
    title: str
    status: str = ""
    created_at: str = ""
    client_name: str = ""
    hourly_rate: float | None = None
    total_hours: float | None = None
    total_charge: float | None = None

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Contract":
        return cls(
            id=data.get("reference", ""),
            title=data.get("job", {}).get("title", data.get("engagement_title", "")),
            status=data.get("status", ""),
            created_at=data.get("created_time", ""),
            client_name=data.get("buyer", {}).get("company_name", ""),
            hourly_rate=data.get("hourly_charge_rate", {}).get("amount"),
            total_hours=data.get("hours_per_week"),
            total_charge=data.get("total_charge", {}).get("amount"),
        )


@dataclass
class EarningRow:
    """One line of an earnings report.

    The API returns rows three ways: a Google-Charts style object with a
    ``c`` list of ``{"v": value}`` cells, a flat object with named keys, or
    a bare list of values in column order. ``from_api`` absorbs all three so
    no caller has to.
    """

    date: str = ""
    client: str = ""
    contract: str = ""
    amount: float = 0.0
    kind: str = ""

    #: Column order used by the bare-list and cell-array shapes.
    COLUMNS = ("Date", "Client", "Contract", "Amount", "Type")

    @classmethod
    def from_api(cls, row: Any) -> "EarningRow":
        if isinstance(row, dict):
            cells = row.get("c")
            if isinstance(cells, list) and cells:
                values = [
                    (c or {}).get("v", "") if isinstance(c, dict) else c for c in cells
                ]
                return cls._from_values(values)
            return cls(
                date=str(row.get("date", row.get("worked_on", "")) or ""),
                client=str(row.get("client", row.get("buyer_company_name", "")) or ""),
                contract=str(
                    row.get("contract", row.get("engagement_title", "")) or ""
                ),
                amount=_to_float(
                    row.get("amount", row.get("charge_amount", row.get("total_charge")))
                ),
                kind=str(row.get("type", row.get("subtype", "")) or ""),
            )
        if isinstance(row, list):
            return cls._from_values(row)
        return cls()

    @classmethod
    def _from_values(cls, values: list[Any]) -> "EarningRow":
        def at(i: int) -> str:
            return str(values[i]) if i < len(values) else ""

        return cls(
            date=at(0),
            client=at(1),
            contract=at(2),
            amount=_to_float(values[3] if len(values) > 3 else None),
            kind=at(4),
        )

    def as_cells(self) -> list[str]:
        """The row as display/CSV cells, in ``COLUMNS`` order."""
        return [
            self.date,
            self.client,
            self.contract,
            f"{self.amount:.2f}" if self.amount else "",
            self.kind,
        ]


@dataclass
class EarningsSummary:
    """Totals over a set of earning rows."""

    total: float = 0.0
    this_month: float = 0.0
    this_week: float = 0.0


@dataclass
class Room:
    """A message conversation.

    The API returns rooms in several shapes -- keys differ, and single
    results arrive unwrapped -- so ``from_api`` is where those differences
    are absorbed rather than at each display site.
    """

    id: str
    participants: list[str] = field(default_factory=list)
    last_message: str = ""
    updated_at: str = ""

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Room":
        roster = data.get("roster") or []
        if isinstance(roster, dict):
            roster = roster.get("user") or []
        if isinstance(roster, dict):
            roster = [roster]

        recent = data.get("recentMessage", data.get("lastMessage")) or {}
        if isinstance(recent, str):
            preview = recent
        else:
            preview = recent.get("message", recent.get("text", "")) or ""

        return cls(
            id=str(data.get("roomId", data.get("id", "")) or ""),
            participants=[
                u.get("name") or u.get("userId") or "Unknown"
                for u in roster
                if isinstance(u, dict)
            ],
            last_message=preview,
            updated_at=str(
                data.get(
                    "roomUpdatedDate",
                    data.get("updatedAt", data.get("updated_at", "")),
                )
                or ""
            ),
        )


@dataclass
class Message:
    id: str
    room_id: str
    sender_id: str = ""
    sender_name: str = ""
    content: str = ""
    created_at: str = ""

    @property
    def sender_label(self) -> str:
        """Best available way to name the sender when displaying the message."""
        return self.sender_name or self.sender_id or "Unknown"

    @classmethod
    def from_api(cls, data: dict[str, Any], room_id: str = "") -> "Message":
        user = data.get("user") or {}
        return cls(
            id=data.get("id", ""),
            room_id=room_id,
            sender_id=str(data.get("userId") or user.get("id") or ""),
            sender_name=user.get("name") or "",
            content=data.get("message", data.get("text", "")),
            created_at=data.get("createdAt", data.get("created_at", "")),
        )


@dataclass
class Conversation:
    """A room's messages together with who is reading them.

    Carrying the viewer alongside the messages means a caller never has to
    look up its own user id before rendering, and a Message is never asked
    a question -- "is this mine?" -- that it cannot answer on its own.
    """

    room_id: str
    messages: list[Message] = field(default_factory=list)
    viewer_id: str = ""

    def is_own(self, message: Message) -> bool:
        return bool(self.viewer_id) and message.sender_id == self.viewer_id
