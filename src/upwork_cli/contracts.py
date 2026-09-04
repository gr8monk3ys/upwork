"""Contracts and engagements: work already won, read back from Upwork.

The earnings slice went behind a module in #26; the contracts group in the
same command file did not, and kept calling the client directly, unwrapping
four payload shapes inline and swallowing ``Exception``.

Owned by Upwork. This module can read a Contract and submit work against one,
nothing more. Failures are raised, not printed.
"""

from typing import Any

from upwork_cli.client import UpworkClient
from upwork_cli.models import Contract, ContractDetail, Milestone


class ContractsError(RuntimeError):
    """Raised when Upwork cannot answer a contract request."""


def _engagements(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    """The engagement nodes inside a list payload.

    Upwork returns this four different ways depending on how many there are,
    including a bare dict for exactly one.
    """
    data = payload or {}
    found = (
        (data.get("engagements") or {}).get("engagement")
        if isinstance(data.get("engagements"), dict)
        else None
    )
    if found is None:
        found = data.get("engagement") or data.get("engagements") or []
    if isinstance(found, dict):
        return [found]
    return [item for item in found if isinstance(item, dict)]


def _milestones(payload: dict[str, Any]) -> list[Milestone]:
    """The milestones inside one engagement's detail payload."""
    found = payload.get("milestones", payload.get("fixed_price_milestones", []))
    if isinstance(found, dict):
        found = found.get("milestone", found)
    if isinstance(found, dict):
        found = [found]
    return [Milestone.from_api(item) for item in found or [] if isinstance(item, dict)]


def list_contracts(client: UpworkClient) -> list[Contract]:
    """Every contract Upwork lists for the freelancer."""
    try:
        payload = client.get_engagements()
    except Exception as exc:
        raise ContractsError(f"Failed to fetch contracts: {exc}") from exc
    return [Contract.from_api(node) for node in _engagements(payload)]


def get_contract(client: UpworkClient, reference: str) -> ContractDetail:
    """One contract with its milestones."""
    try:
        payload = client.get_engagement(reference)
    except Exception as exc:
        raise ContractsError(f"Failed to fetch contract: {exc}") from exc
    engagement = (payload or {}).get("engagement", payload) or {}
    return ContractDetail(
        contract=Contract.from_api(engagement),
        milestones=_milestones(engagement),
    )


def submit_work(client: UpworkClient, reference: str, message: str = "") -> None:
    """Submit work against a contract's current milestone."""
    params: dict[str, Any] = {"engagement__reference": reference}
    if message:
        params["comments"] = message
    try:
        client.submit_work(params)
    except Exception as exc:
        raise ContractsError(f"Failed to submit work: {exc}") from exc
