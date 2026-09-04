"""Tests for the transport dialects the Upwork client keeps to itself.

These strings used to be built by the domain modules, so a caller of the
seam had to know Upwork's paging format and its report query language. They
are built here now, and this is where they are pinned.
"""

from unittest.mock import MagicMock, patch

import pytest

from upwork_cli.client import UpworkClient, check_callback_url
from upwork_cli.config import AuthToken, Settings


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


class TestConfigAndAuth:
    def test_an_unauthenticated_client_says_so(self, isolated_config):
        assert UpworkClient(settings=Settings()).is_authenticated is False

    def test_a_token_makes_it_authenticated(self, isolated_config):
        token = AuthToken(access_token="a", refresh_token="r", expires_at=0)
        assert UpworkClient(settings=Settings(), token=token).is_authenticated

    def test_the_config_carries_the_credentials(self, isolated_config):
        upwork = UpworkClient(
            settings=Settings(client_id="cid", redirect_uri="https://cb")
        )
        config = upwork._get_config()
        assert config["client_id"] == "cid"
        assert config["redirect_uri"] == "https://cb"
        assert "token" not in config  # nothing to carry yet

    def test_the_config_carries_a_token_when_there_is_one(self, isolated_config):
        token = AuthToken(access_token="a", refresh_token="r", expires_at=0)
        config = UpworkClient(settings=Settings(), token=token)._get_config()
        assert config["token"]["access_token"] == "a"

    def test_the_underlying_client_is_built_once(self, isolated_config):
        upwork = UpworkClient(settings=Settings(client_id="cid"))
        with patch("upwork_cli.client.upwork") as sdk:
            first = upwork._ensure_client()
            second = upwork._ensure_client()
        assert first is second
        assert sdk.Client.call_count == 1

    def test_completing_auth_stores_the_token(self, isolated_config):
        upwork = UpworkClient(settings=Settings(client_id="cid"))
        sdk = MagicMock()
        sdk.get_access_token.return_value = {
            "access_token": "at",
            "refresh_token": "rt",
            "token_type": "Bearer",
            "expires_at": 123.0,
        }
        with patch.object(upwork, "_ensure_client", return_value=sdk):
            token = upwork.complete_auth("https://cb?code=x")
        assert token.access_token == "at"
        assert upwork.is_authenticated
        from upwork_cli.config import load_auth

        assert load_auth().refresh_token == "rt"

    def test_the_authorization_url_comes_from_the_sdk(self, client):
        sdk = MagicMock()
        sdk.get_authorization_url.return_value = ("https://auth", "state")
        with patch.object(client, "_ensure_client", return_value=sdk):
            assert client.get_authorization_url() == "https://auth"


class TestGraphQLErrors:
    def test_data_is_returned_when_there_are_no_errors(self, client):
        with patch.object(client, "_graphql", return_value={"data": {"a": 1}}):
            assert client._graphql_data("query", {}) == {"a": 1}

    def test_one_error_is_raised_with_its_message(self, client):
        payload = {"errors": [{"message": "field unknown"}]}
        with (
            patch.object(client, "_graphql", return_value=payload),
            pytest.raises(RuntimeError, match="field unknown"),
        ):
            client._graphql_data("query", {})

    def test_several_errors_are_joined(self, client):
        payload = {"errors": [{"message": "one"}, {"message": "two"}]}
        with (
            patch.object(client, "_graphql", return_value=payload),
            pytest.raises(RuntimeError, match="one; two"),
        ):
            client._graphql_data("query", {})

    def test_a_non_dict_error_still_reports(self, client):
        with (
            patch.object(client, "_graphql", return_value={"errors": ["boom"]}),
            pytest.raises(RuntimeError, match="boom"),
        ):
            client._graphql_data("query", {})

    def test_a_missing_data_key_is_an_empty_dict(self, client):
        with patch.object(client, "_graphql", return_value={}):
            assert client._graphql_data("query", {}) == {}


class TestJobSearchQuery:
    def test_the_search_term_and_paging_reach_the_query(self, client):
        with patch.object(client, "_graphql", return_value={}) as graphql:
            client.search_jobs_graphql("python scraper", limit=7)
            query, variables = graphql.call_args.args
        assert variables["searchTerm"] == "python scraper"
        assert "first: 7" in query

    def test_sort_defaults_to_newest_first(self, client):
        with patch.object(client, "_graphql", return_value={}) as graphql:
            client.search_jobs_graphql("python")
            variables = graphql.call_args.args[1]
        assert variables["sortField"] == "CREATE_TIME"
        assert variables["sortOrder"] == "DESC"


class TestOfferQuery:
    def test_state_and_search_narrow_the_filter(self, client):
        with patch.object(client, "_graphql_data", return_value={}) as graphql:
            client.get_offers(state="Pending", search_text="api", limit=5)
            variables = graphql.call_args.args[1]
        common = variables["filter"]["commonFilter"]
        assert common["states_any"] == ["Pending"]
        assert common["text_eq"] == "api"
        assert variables["pagination"]["first"] == 5

    def test_no_filters_sends_no_filter_block(self, client):
        with patch.object(client, "_graphql_data", return_value={}) as graphql:
            client.get_offers()
            variables = graphql.call_args.args[1]
        assert "commonFilter" not in variables.get("filter", {})


class TestCallbackUrlGuidance:
    """Pasting the authorize URL back is the mistake this flow invites.

    Upwork answers it with "(missing_code) Missing code parameter in
    response", which names what is absent but not what to do about it.
    """

    AUTHORIZE = (
        "https://www.upwork.com/ab/account-security/oauth2/authorize"
        "?response_type=code&client_id=abc"
        "&redirect_uri=https%3A%2F%2Flocalhost%3A8080%2Fcallback&state=xyz"
    )
    CALLBACK = "https://localhost:8080/callback?code=abc123&state=xyz"

    def test_a_real_callback_passes(self):
        check_callback_url(self.CALLBACK)  # does not raise

    def test_the_authorize_url_is_named_as_such(self):
        with pytest.raises(ValueError, match="authorization URL, not the callback"):
            check_callback_url(self.AUTHORIZE)

    def test_the_expected_connection_failure_is_explained(self):
        """The browser failing to reach localhost:8080 is the success case."""
        with pytest.raises(ValueError) as exc:
            check_callback_url(self.AUTHORIZE)
        assert "expected" in str(exc.value)
        assert "address bar" in str(exc.value)

    def test_a_denied_authorization_says_so(self):
        with pytest.raises(
            ValueError, match="refused the authorization: access_denied"
        ):
            check_callback_url("https://localhost:8080/callback?error=access_denied")

    def test_an_unrelated_url_is_refused(self):
        with pytest.raises(ValueError, match="no `code=` parameter"):
            check_callback_url("https://example.com/")

    def test_an_empty_paste_is_refused(self):
        with pytest.raises(ValueError, match="No URL given"):
            check_callback_url("   ")

    def test_surrounding_whitespace_is_tolerated(self):
        check_callback_url(f"  {self.CALLBACK}  ")

    def test_complete_auth_refuses_before_calling_upwork(self, client):
        """The check runs first, so a bad paste costs no network round trip."""
        sdk = MagicMock()
        with (
            patch.object(client, "_ensure_client", return_value=sdk),
            pytest.raises(ValueError),
        ):
            client.complete_auth(self.AUTHORIZE)
        assert sdk.get_access_token.call_count == 0
