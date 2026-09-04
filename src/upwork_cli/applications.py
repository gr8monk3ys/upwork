"""Reading submitted applications and the offers that follow them.

Sits between the commands and ``UpworkClient``: the client returns GraphQL
connection payloads, and this module turns them into Applications and Offers.
Failures are raised, not printed.

An Application here is one already submitted on Upwork and read back from its
API -- distinct from a locally drafted Proposal, which Upwork's terms forbid
submitting programmatically.
"""

from typing import Any

from upwork_cli.client import UpworkClient
from upwork_cli.models import Application, Offer


class ApplicationsError(RuntimeError):
    """Raised when the Upwork API cannot answer an applications request."""


def _nodes(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    """The nodes of a GraphQL connection payload."""
    edges = (payload or {}).get("edges") or []
    return [
        edge.get("node") or {}
        for edge in edges
        if isinstance(edge, dict) and edge.get("node")
    ]


#: Domain sort name -> the Upwork enum that asks for it. The mapping lives
#: behind this seam so callers name the ordering they want and never the
#: transport's spelling of it.
SORT_FIELDS = {
    "created": "CreatedDateTime",
    "modified": "ModifiedDateTime",
    "status": "StatusChangedDateTime",
}


def list_applications(
    client: UpworkClient,
    statuses: list[str],
    limit: int = 20,
    sort: str = "modified",
) -> list[Application]:
    """Applications across one or more statuses, newest first, deduplicated.

    Upwork's API filters by a single status, so several calls are made and
    their results merged: the same application can come back under more than
    one status.

    *sort* is a domain name from :data:`SORT_FIELDS`, and orders both the
    request and the merged result. Asking the API for one ordering and then
    sorting the merge by another silently ignored ``status``.
    """
    sort_field = SORT_FIELDS.get(sort, SORT_FIELDS["modified"])
    found: dict[str, Application] = {}
    for status in statuses:
        try:
            payload = client.get_applications(
                status=status, limit=limit, sort_field=sort_field
            )
        except Exception as exc:
            raise ApplicationsError(f"Failed to fetch applications: {exc}") from exc

        for node in _nodes(payload):
            application = Application.from_api(node)
            if application.id and application.id not in found:
                found[application.id] = application

    ordered = sorted(found.values(), key=lambda a: a.sort_key(sort), reverse=True)
    return ordered[:limit]


def get_application(client: UpworkClient, application_id: str) -> Application | None:
    """One application, or None when Upwork does not know it."""
    try:
        payload = client.get_application(application_id)
    except Exception as exc:
        raise ApplicationsError(
            f"Failed to fetch application {application_id}: {exc}"
        ) from exc
    return Application.from_api(payload) if payload else None


def offers_for_application(
    client: UpworkClient, application_id: str, limit: int = 10
) -> list[Offer]:
    """Offers extended off the back of one application."""
    try:
        results = client.get_offers_for_application(application_id, limit=limit)
    except Exception as exc:
        raise ApplicationsError(
            f"Failed to fetch offers for application {application_id}: {exc}"
        ) from exc
    return [Offer.from_api(item) for item in results or []]


def list_offers(
    client: UpworkClient, state: str | None = None, limit: int = 20
) -> list[Offer]:
    """Current offers, optionally filtered by state."""
    try:
        payload = client.get_offers(limit=limit, state=state)
    except Exception as exc:
        raise ApplicationsError(f"Failed to fetch offers: {exc}") from exc

    offers = [Offer.from_api(node) for node in _nodes(payload)]
    return [offer for offer in offers if offer.id]


def get_offer(client: UpworkClient, offer_id: str) -> Offer | None:
    """One offer, or None when Upwork does not know it."""
    try:
        payload = client.get_offer(offer_id)
    except Exception as exc:
        raise ApplicationsError(f"Failed to fetch offer {offer_id}: {exc}") from exc
    return Offer.from_api(payload) if payload else None


def withdraw_offer(
    client: UpworkClient, offer_id: str, reason: str, message: str | None = None
) -> None:
    """Withdraw from an offer."""
    try:
        client.withdraw_offer(offer_id, reason=reason, message=message or None)
    except Exception as exc:
        raise ApplicationsError(f"Failed to withdraw offer: {exc}") from exc
