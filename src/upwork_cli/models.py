"""Data models for Upwork API responses."""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class JobPosting:
    id: str
    title: str
    description: str = ""
    skills: list[str] = field(default_factory=list)
    budget_amount: Optional[float] = None
    budget_currency: str = "USD"
    duration: str = ""
    duration_label: str = ""
    engagement: str = ""
    created_at: str = ""
    client_country: str = ""
    client_total_spent: Optional[float] = None
    client_total_hires: Optional[int] = None
    client_feedback: Optional[float] = None
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

    def to_db_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "skills": self.skills,
            "budget_amount": self.budget_amount,
            "budget_currency": self.budget_currency,
            "duration": self.duration,
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
        if self.duration_label:
            parts.append(f"Duration: {self.duration_label}")
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
class Contract:
    id: str
    title: str
    status: str = ""
    created_at: str = ""
    client_name: str = ""
    hourly_rate: Optional[float] = None
    total_hours: Optional[float] = None
    total_charge: Optional[float] = None

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
class Message:
    id: str
    room_id: str
    sender: str = ""
    content: str = ""
    created_at: str = ""

    @classmethod
    def from_api(cls, data: dict[str, Any], room_id: str = "") -> "Message":
        return cls(
            id=data.get("id", ""),
            room_id=room_id,
            sender=data.get("userId", data.get("user", {}).get("name", "")),
            content=data.get("message", data.get("text", "")),
            created_at=data.get("createdAt", data.get("created_at", "")),
        )
