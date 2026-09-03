"""In-memory stand-ins for external services.

``FakeUpworkClient`` is the second implementation behind the Upwork seam:
``UpworkClient`` talks to the API, this one answers from payloads handed to
it. Tests construct one instead of assembling a MagicMock per test.
"""

from typing import Any


class FakeUpworkClient:
    """An UpworkClient that answers from canned payloads.

    Every argument is optional, so a test states only what it cares about.
    Pass an ``Exception`` instance in place of a payload to make that call
    raise instead of return.
    """

    def __init__(
        self,
        *,
        authenticated: bool = True,
        user_id: str = "~user001",
        company_id: str = "comp-123",
        companies: Any = None,
        user_info: Any = None,
        rooms: Any = None,
        messages: Any = None,
        room_by_contract: Any = None,
        earnings: Any = None,
        applications: Any = None,
        application: Any = None,
        offers: Any = None,
        offer: Any = None,
        offers_for_application: Any = None,
    ) -> None:
        self.is_authenticated = authenticated
        self._companies = (
            companies
            if companies is not None
            else {"companies": {"company": [{"company_id": company_id}]}}
        )
        self._user_info = (
            user_info if user_info is not None else {"info": {"ref": user_id}}
        )
        self._rooms = rooms if rooms is not None else {"rooms": []}
        self._messages = messages if messages is not None else {"stories": []}
        self._room_by_contract = (
            room_by_contract if room_by_contract is not None else {"room": {}}
        )
        self._earnings = earnings if earnings is not None else {"table": {"rows": []}}
        self.sent: list[tuple[str, str, dict[str, Any]]] = []
        self._applications = applications if applications is not None else {"edges": []}
        self._application = application if application is not None else {}
        self._offers = offers if offers is not None else {"edges": []}
        self._offer = offer if offer is not None else {}
        self._offers_for_application = (
            offers_for_application if offers_for_application is not None else []
        )
        self.earnings_params: list[Any] = []
        self.application_queries: list[Any] = []
        self.offer_queries: list[Any] = []
        self.withdrawn: list[tuple[str, str, Any]] = []

    @staticmethod
    def _answer(value: Any) -> Any:
        if isinstance(value, Exception):
            raise value
        return value

    # --- the messaging slice of the interface ---

    def get_companies(self) -> Any:
        return self._answer(self._companies)

    def get_user_info(self) -> Any:
        return self._answer(self._user_info)

    def get_rooms(self, company: str, params: dict[str, Any] | None = None) -> Any:
        return self._answer(self._rooms)

    def get_room_messages(
        self, company: str, room_id: str, params: dict[str, Any] | None = None
    ) -> Any:
        return self._answer(self._messages)

    def get_room_by_contract(
        self, company: str, contract_id: str, params: dict[str, Any] | None = None
    ) -> Any:
        return self._answer(self._room_by_contract)

    # --- the earnings slice of the interface ---

    def get_earnings(
        self, freelancer_ref: str, params: dict[str, Any] | None = None
    ) -> Any:
        self.earnings_params.append(params)
        return self._answer(self._earnings)

    # --- the applications and offers slice of the interface ---

    def get_applications(self, params: dict[str, Any] | None = None) -> Any:
        self.application_queries.append(params)
        return self._answer(self._applications)

    def get_application(self, reference: str) -> Any:
        return self._answer(self._application)

    def get_offers_for_application(self, reference: str, limit: int = 10) -> Any:
        return self._answer(self._offers_for_application)

    def get_offers(self, params: dict[str, Any] | None = None) -> Any:
        self.offer_queries.append(params)
        return self._answer(self._offers)

    def get_offer(self, reference: str) -> Any:
        return self._answer(self._offer)

    def withdraw_offer(
        self, reference: str, reason: str, message: str | None = None
    ) -> bool:
        if isinstance(self._offer, Exception):
            raise self._offer
        self.withdrawn.append((reference, reason, message))
        return True

    def send_message(
        self, company: str, room_id: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        if isinstance(self._messages, Exception):
            raise self._messages
        self.sent.append((company, room_id, params))
        return {"status": "ok"}


def room_payload(
    room_id: str = "room-1",
    *,
    participants: list[str] | None = None,
    preview: str = "Hello there",
    updated: str = "2026-09-01T10:00:00Z",
) -> dict[str, Any]:
    """One room as the API returns it."""
    return {
        "roomId": room_id,
        "roster": [{"name": name} for name in (participants or ["Dana Reyes"])],
        "recentMessage": {"message": preview},
        "roomUpdatedDate": updated,
    }


def message_payload(
    message_id: str = "msg-1",
    *,
    sender_id: str = "~other",
    sender_name: str = "Dana Reyes",
    text: str = "Hello there",
    created: str = "2026-09-01T10:00:00Z",
) -> dict[str, Any]:
    """One message as the API returns it."""
    return {
        "id": message_id,
        "userId": sender_id,
        "user": {"id": sender_id, "name": sender_name},
        "message": text,
        "createdAt": created,
    }


def earnings_payload(*rows: Any, cols: list[str] | None = None) -> dict[str, Any]:
    """An earnings report as the API returns it, Google-Charts style."""
    payload: dict[str, Any] = {"table": {"rows": list(rows)}}
    if cols is not None:
        payload["table"]["cols"] = [{"label": c} for c in cols]
    return payload


def earning_cells(
    date: str = "2026-09-01",
    client: str = "Acme Corp",
    contract: str = "API work",
    amount: str = "1200.00",
    kind: str = "Fixed",
) -> dict[str, Any]:
    """One row in the cell-array shape."""
    return {
        "c": [{"v": date}, {"v": client}, {"v": contract}, {"v": amount}, {"v": kind}]
    }


def earning_flat(
    date: str = "2026-09-01",
    client: str = "Acme Corp",
    contract: str = "API work",
    amount: str = "1200.00",
    kind: str = "Fixed",
) -> dict[str, Any]:
    """The same row in the flat-dict shape."""
    return {
        "date": date,
        "buyer_company_name": client,
        "engagement_title": contract,
        "charge_amount": amount,
        "subtype": kind,
    }


def connection(*nodes: Any) -> dict[str, Any]:
    """Wrap nodes as a GraphQL connection payload."""
    return {"edges": [{"node": n} for n in nodes]}


def application_node(
    application_id: str = "app-1",
    *,
    status: str = "Submitted",
    job_title: str = "Build an API",
    cover_letter: str = "I would be a great fit.",
    created: str = "2026-09-01T10:00:00Z",
    modified: str = "2026-09-02T10:00:00Z",
) -> dict[str, Any]:
    """One application as the GraphQL API returns it."""
    return {
        "id": application_id,
        "status": {"status": status},
        "proposalCoverLetter": cover_letter,
        "auditDetails": {
            "createdDateTime": created,
            "modifiedDateTime": modified,
            "statusChangedDateTime": modified,
        },
        "marketplaceJobPosting": {
            "id": "job-1",
            "title": job_title,
            "amount": {"amount": "3000", "currencyCode": "USD"},
        },
    }


def offer_node(
    offer_id: str = "offer-1",
    *,
    title: str = "Backend work",
    state: str = "ACTIVE",
    kind: str = "FIXED",
    client_name: str = "Acme Corp",
    budget: str | None = "5000",
    hourly_rate: str | None = None,
    weekly_limit: int | None = None,
) -> dict[str, Any]:
    """One offer as the GraphQL API returns it, wrapped as a connection node."""
    if hourly_rate is not None:
        terms: dict[str, Any] = {
            "hourlyTerms": {
                "rate": {"amount": hourly_rate, "currencyCode": "USD"},
                "weeklyHoursLimit": weekly_limit,
            }
        }
    elif budget is not None:
        terms = {
            "fixedPriceTerm": {"budget": {"amount": budget, "currencyCode": "USD"}}
        }
    else:
        terms = {}

    return {
        "offer": {"id": offer_id},
        "title": title,
        "state": state,
        "type": kind,
        "company": {"name": client_name},
        "offerTerms": terms,
        "lastUpdatedDateTime": "2026-09-02T10:00:00Z",
    }
