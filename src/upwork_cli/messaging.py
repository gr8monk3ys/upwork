"""Reading and sending Upwork messages.

Sits between the commands and ``UpworkClient``: the client returns raw API
payloads, and this module turns them into Rooms, Messages and Conversations.
Callers never see a payload shape, and never have to resolve the account's
company reference or their own user id before asking a question.

Failures are raised, not printed. Presentation belongs to the command.
"""

from typing import Any

from upwork_cli.client import UpworkClient
from upwork_cli.models import Conversation, Message, Room


class MessagingError(RuntimeError):
    """Raised when the Upwork API cannot answer a messaging request."""


def _as_list(value: Any, *keys: str) -> list[dict[str, Any]]:
    """Normalise a payload collection that may arrive in several shapes.

    The API returns a list, a bare object when there is one result, or an
    object wrapping the list under a singular key -- sometimes all three for
    the same endpoint.
    """
    if isinstance(value, dict):
        for key in keys:
            if key in value:
                value = value[key]
                break
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _company(client: UpworkClient) -> str:
    """The account's company reference, which every messaging call needs."""
    try:
        result = client.get_companies()
    except Exception as exc:
        raise MessagingError(f"Failed to retrieve company info: {exc}") from exc

    companies = _as_list(result.get("companies"), "company")
    if not companies:
        raise MessagingError("No companies found for your account.")
    first = companies[0]
    reference = first.get("company_id") or first.get("reference") or ""
    if not reference:
        raise MessagingError("Company record has no usable reference.")
    return str(reference)


def _viewer_id(client: UpworkClient) -> str:
    """The current user's id, used to tell their own messages apart.

    Returns an empty string when it cannot be determined: not knowing who
    you are makes every message render as someone else's, which is a worse
    display than failing the whole command.
    """
    try:
        info = client.get_user_info()
    except Exception:  # noqa: BLE001 - any failure here degrades, never aborts
        return ""
    return str(info.get("info", {}).get("ref", info.get("id", "")) or "")


def _messages_in(
    client: UpworkClient, company: str, room_id: str, limit: int
) -> list[Message]:
    try:
        result = client.get_room_messages(company, room_id, {"paging": f"0;{limit}"})
    except Exception as exc:
        raise MessagingError(f"Failed to fetch messages: {exc}") from exc

    entries = _as_list(
        result.get("stories", result.get("messages")), "story", "message"
    )
    return [Message.from_api(entry, room_id=room_id) for entry in entries]


def list_rooms(client: UpworkClient, limit: int = 20) -> list[Room]:
    """Recent conversations, most recently updated first."""
    company = _company(client)
    try:
        result = client.get_rooms(company, {"paging": f"0;{limit}"})
    except Exception as exc:
        raise MessagingError(f"Failed to fetch rooms: {exc}") from exc

    rooms = _as_list(result.get("rooms"), "room")
    return [Room.from_api(room) for room in rooms[:limit]]


def read_room(client: UpworkClient, room_id: str, limit: int = 50) -> Conversation:
    """A room's recent messages, with the reader's identity attached."""
    company = _company(client)
    return Conversation(
        room_id=room_id,
        messages=_messages_in(client, company, room_id, limit),
        viewer_id=_viewer_id(client),
    )


def send_message(client: UpworkClient, room_id: str, text: str) -> None:
    """Post *text* to a room."""
    company = _company(client)
    try:
        client.send_message(company, room_id, {"message": text})
    except Exception as exc:
        raise MessagingError(f"Failed to send message: {exc}") from exc


def find_room_for_contract(
    client: UpworkClient, contract: str, limit: int = 20
) -> Conversation | None:
    """The conversation attached to a contract, or None if there is none."""
    company = _company(client)
    try:
        result = client.get_room_by_contract(company, contract)
    except Exception as exc:
        raise MessagingError(
            f"Failed to find room for contract {contract}: {exc}"
        ) from exc

    rooms = _as_list(result.get("room", result), "room")
    room_id = str(rooms[0].get("roomId", rooms[0].get("id", "")) or "") if rooms else ""
    if not room_id:
        return None

    return Conversation(
        room_id=room_id,
        messages=_messages_in(client, company, room_id, limit),
        viewer_id=_viewer_id(client),
    )
