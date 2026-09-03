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
        self.earnings_params: list[Any] = []

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
