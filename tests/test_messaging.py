"""Tests for upwork_cli.messaging.

These go through the module's own interface with a FakeUpworkClient, rather
than driving the CLI and asserting on rendered output. Payload-shape
handling lives here, so this is where the shapes are exercised.
"""

import pytest

from tests.fakes import FakeUpworkClient, message_payload, room_payload
from upwork_cli import messaging


class TestCompanyResolution:
    def test_nested_dict_structure(self):
        client = FakeUpworkClient(
            companies={"companies": {"company": [{"company_id": "comp-123"}]}},
            rooms={"rooms": []},
        )
        assert messaging.list_rooms(client) == []

    def test_list_structure(self):
        client = FakeUpworkClient(companies={"companies": [{"company_id": "c-9"}]})
        assert messaging.list_rooms(client) == []

    def test_single_company_object(self):
        client = FakeUpworkClient(companies={"companies": {"company_id": "solo"}})
        assert messaging.list_rooms(client) == []

    def test_reference_key_is_accepted(self):
        client = FakeUpworkClient(companies={"companies": [{"reference": "ref-1"}]})
        assert messaging.list_rooms(client) == []

    def test_no_companies_raises(self):
        client = FakeUpworkClient(companies={"companies": []})
        with pytest.raises(messaging.MessagingError, match="No companies"):
            messaging.list_rooms(client)

    def test_api_error_raises(self):
        client = FakeUpworkClient(companies=RuntimeError("upstream down"))
        with pytest.raises(messaging.MessagingError, match="company info"):
            messaging.list_rooms(client)


class TestListRooms:
    def test_returns_rooms(self):
        client = FakeUpworkClient(
            rooms={"rooms": [room_payload("r-1", participants=["Dana", "Sam"])]}
        )
        rooms = messaging.list_rooms(client)
        assert [r.id for r in rooms] == ["r-1"]
        assert rooms[0].participants == ["Dana", "Sam"]
        assert rooms[0].last_message == "Hello there"
        assert rooms[0].updated_at == "2026-09-01T10:00:00Z"

    def test_no_rooms(self):
        assert messaging.list_rooms(FakeUpworkClient(rooms={"rooms": []})) == []

    def test_singular_wrapper_shape(self):
        client = FakeUpworkClient(rooms={"rooms": {"room": [room_payload("r-2")]}})
        assert [r.id for r in messaging.list_rooms(client)] == ["r-2"]

    def test_single_bare_object_shape(self):
        client = FakeUpworkClient(rooms={"rooms": room_payload("r-3")})
        assert [r.id for r in messaging.list_rooms(client)] == ["r-3"]

    def test_limit_is_applied(self):
        client = FakeUpworkClient(
            rooms={"rooms": [room_payload(f"r-{i}") for i in range(5)]}
        )
        assert len(messaging.list_rooms(client, limit=2)) == 2

    def test_api_error_raises(self):
        client = FakeUpworkClient(rooms=RuntimeError("boom"))
        with pytest.raises(messaging.MessagingError, match="fetch rooms"):
            messaging.list_rooms(client)


class TestReadRoom:
    def test_returns_messages_with_the_viewer(self):
        client = FakeUpworkClient(
            user_id="~me",
            messages={
                "stories": [
                    message_payload("m1", sender_id="~me", sender_name="Me"),
                    message_payload("m2", sender_id="~them", sender_name="Dana"),
                ]
            },
        )
        convo = messaging.read_room(client, "r-1")
        assert convo.room_id == "r-1"
        assert [m.id for m in convo.messages] == ["m1", "m2"]
        assert convo.viewer_id == "~me"
        assert convo.is_own(convo.messages[0]) is True
        assert convo.is_own(convo.messages[1]) is False

    def test_names_are_preserved(self):
        client = FakeUpworkClient(
            messages={"stories": [message_payload(sender_name="Dana Reyes")]}
        )
        assert messaging.read_room(client, "r").messages[0].sender_label == "Dana Reyes"

    def test_empty_room(self):
        client = FakeUpworkClient(messages={"stories": []})
        assert messaging.read_room(client, "r").messages == []

    def test_singular_wrapper_shape(self):
        client = FakeUpworkClient(messages={"stories": {"story": [message_payload()]}})
        assert len(messaging.read_room(client, "r").messages) == 1

    def test_messages_key_variant(self):
        client = FakeUpworkClient(messages={"messages": [message_payload()]})
        assert len(messaging.read_room(client, "r").messages) == 1

    def test_api_error_raises(self):
        client = FakeUpworkClient(messages=RuntimeError("nope"))
        with pytest.raises(messaging.MessagingError, match="fetch messages"):
            messaging.read_room(client, "r")

    def test_unknown_viewer_marks_nothing_as_own(self):
        """A failed identity lookup degrades rather than aborting the read."""
        client = FakeUpworkClient(
            user_info=RuntimeError("who am i"),
            messages={"stories": [message_payload(sender_id="~someone")]},
        )
        convo = messaging.read_room(client, "r")
        assert convo.viewer_id == ""
        assert convo.is_own(convo.messages[0]) is False


class TestSendMessage:
    def test_posts_to_the_room(self):
        client = FakeUpworkClient()
        messaging.send_message(client, "r-1", "hello")
        assert client.sent == [("comp-123", "r-1", {"message": "hello"})]

    def test_api_error_raises(self):
        client = FakeUpworkClient(messages=RuntimeError("rejected"))
        with pytest.raises(messaging.MessagingError, match="send message"):
            messaging.send_message(client, "r-1", "hello")


class TestFindRoomForContract:
    def test_found(self):
        client = FakeUpworkClient(
            room_by_contract={"room": room_payload("r-7")},
            messages={"stories": [message_payload()]},
        )
        convo = messaging.find_room_for_contract(client, "c-1")
        assert convo is not None
        assert convo.room_id == "r-7"
        assert len(convo.messages) == 1

    def test_not_found(self):
        client = FakeUpworkClient(room_by_contract={"room": {}})
        assert messaging.find_room_for_contract(client, "c-1") is None

    def test_list_shape(self):
        client = FakeUpworkClient(room_by_contract={"room": [room_payload("r-8")]})
        convo = messaging.find_room_for_contract(client, "c-1")
        assert convo is not None and convo.room_id == "r-8"

    def test_api_error_raises(self):
        client = FakeUpworkClient(room_by_contract=RuntimeError("gone"))
        with pytest.raises(messaging.MessagingError, match="find room"):
            messaging.find_room_for_contract(client, "c-1")
