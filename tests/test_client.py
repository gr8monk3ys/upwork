"""Tests for the transport dialects the Upwork client keeps to itself.

These strings used to be built by the domain modules, so a caller of the
seam had to know Upwork's paging format and its report query language. They
are built here now, and this is where they are pinned.
"""

from unittest.mock import MagicMock, patch

import pytest

from upwork_cli.client import UpworkClient
from upwork_cli.config import Settings


@pytest.fixture
def client(monkeypatch):
    upwork = UpworkClient(settings=Settings(client_id="id"))
    monkeypatch.setattr(upwork, "_ensure_client", lambda: MagicMock())
    return upwork


class TestPaging:
    def test_paging_is_offset_semicolon_count(self, client):
        assert client._paging(20) == {"paging": "0;20"}

    def test_get_rooms_sends_the_paging_string(self, client):
        with patch("upwork_cli.client.upwork_messages") as api:
            client.get_rooms("comp-1", limit=15)
            assert api.Api.return_value.get_rooms.call_args.args[1] == {
                "paging": "0;15"
            }

    def test_get_room_messages_sends_the_paging_string(self, client):
        with patch("upwork_cli.client.upwork_messages") as api:
            client.get_room_messages("comp-1", "room-1", limit=5)
            assert api.Api.return_value.get_room_messages.call_args.args[2] == {
                "paging": "0;5"
            }


class TestEarningsQuery:
    def _params(self, client, **kwargs):
        with patch("upwork_cli.client.fin_earnings") as api:
            client.get_earnings("~free1", **kwargs)
            return api.Api.return_value.get_by_freelancer.call_args.args[1]

    def test_both_dates_become_one_tq_clause(self, client):
        assert self._params(client, from_date="2026-01-01", to_date="2026-06-30") == {
            "tq": "date >= '2026-01-01' AND date <= '2026-06-30'"
        }

    def test_one_date_becomes_one_clause(self, client):
        assert self._params(client, from_date="2026-01-01") == {
            "tq": "date >= '2026-01-01'"
        }

    def test_no_dates_sends_no_query(self, client):
        assert self._params(client) == {}


class TestApplicationSort:
    def test_the_default_sort_field_matches_what_callers_send(self, client):
        """Was ``MODIFIEDDATETIME`` here and ``ModifiedDateTime`` at the caller."""
        with patch.object(client, "_graphql_data", return_value={}) as graphql:
            client.get_applications()
            variables = graphql.call_args.args[1]
        assert variables["sortAttribute"]["field"] == "ModifiedDateTime"

    def test_an_explicit_sort_field_reaches_the_query(self, client):
        with patch.object(client, "_graphql_data", return_value={}) as graphql:
            client.get_applications(sort_field="StatusChangedDateTime")
            variables = graphql.call_args.args[1]
        assert variables["sortAttribute"]["field"] == "StatusChangedDateTime"

    def test_job_posting_ids_narrow_the_filter(self, client):
        with patch.object(client, "_graphql_data", return_value={}) as graphql:
            client.get_applications(job_posting_ids=["~job1"])
            variables = graphql.call_args.args[1]
        assert variables["filter"]["jobPostingIds_any"] == ["~job1"]
