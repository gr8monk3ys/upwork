"""Tests for upwork_cli.applications.

The GraphQL connection unwrapping, the dedup-and-sort across statuses, and
the offer terms branching are exercised here through the module's own
interface rather than by driving the CLI.
"""

import pytest

from tests.fakes import FakeUpworkClient, application_node, connection, offer_node
from upwork_cli import applications
from upwork_cli.models import Application, Offer, OfferTerms


class TestListApplications:
    def test_unwraps_connection_nodes(self):
        client = FakeUpworkClient(
            applications=connection(application_node("a-1", job_title="Build an API"))
        )
        found = applications.list_applications(client, ["Submitted"])
        assert [a.id for a in found] == ["a-1"]
        assert found[0].job_title == "Build an API"

    def test_queries_each_status(self):
        client = FakeUpworkClient(applications=connection())
        applications.list_applications(client, ["Submitted", "Accepted"], limit=5)
        assert [q["status"] for q in client.application_queries] == [
            "Submitted",
            "Accepted",
        ]
        assert client.application_queries[0]["limit"] == 5

    def test_deduplicates_across_statuses(self):
        """The same application can come back under more than one status."""
        client = FakeUpworkClient(applications=connection(application_node("a-1")))
        found = applications.list_applications(client, ["Submitted", "Accepted"])
        assert [a.id for a in found] == ["a-1"]

    def test_sorts_newest_first_by_modified(self):
        client = FakeUpworkClient(
            applications=connection(
                application_node("old", modified="2026-01-01T00:00:00Z"),
                application_node("new", modified="2026-09-01T00:00:00Z"),
            )
        )
        found = applications.list_applications(client, ["Submitted"])
        assert [a.id for a in found] == ["new", "old"]

    def test_sorts_by_created_when_asked(self):
        client = FakeUpworkClient(
            applications=connection(
                application_node(
                    "a", created="2026-09-01T00:00:00Z", modified="2026-01-01T00:00:00Z"
                ),
                application_node(
                    "b", created="2026-01-01T00:00:00Z", modified="2026-09-09T00:00:00Z"
                ),
            )
        )
        found = applications.list_applications(client, ["Submitted"], sort="created")
        assert [a.id for a in found] == ["a", "b"]

    def test_sort_status_orders_by_status_change(self):
        """``--sort status`` used to fall through to modified_at silently."""
        client = FakeUpworkClient(
            applications=connection(
                application_node(
                    "stale",
                    modified="2026-09-09T00:00:00Z",
                    status_changed="2026-01-01T00:00:00Z",
                ),
                application_node(
                    "fresh",
                    modified="2026-01-01T00:00:00Z",
                    status_changed="2026-09-09T00:00:00Z",
                ),
            )
        )
        found = applications.list_applications(client, ["Submitted"], sort="status")
        assert [a.id for a in found] == ["fresh", "stale"]

    def test_sort_name_reaches_the_api_as_its_enum(self):
        client = FakeUpworkClient(applications=connection(application_node("a")))
        applications.list_applications(client, ["Submitted"], sort="status")
        assert client.application_queries[0]["sort_field"] == "StatusChangedDateTime"

    def test_limit_truncates(self):
        client = FakeUpworkClient(
            applications=connection(*[application_node(f"a-{i}") for i in range(5)])
        )
        assert len(applications.list_applications(client, ["Submitted"], limit=2)) == 2

    def test_nodes_without_an_id_are_dropped(self):
        client = FakeUpworkClient(applications=connection({"status": {}}))
        assert applications.list_applications(client, ["Submitted"]) == []

    def test_api_error_raises(self):
        client = FakeUpworkClient(applications=RuntimeError("boom"))
        with pytest.raises(applications.ApplicationsError, match="fetch applications"):
            applications.list_applications(client, ["Submitted"])


class TestGetApplication:
    def test_returns_the_application(self):
        client = FakeUpworkClient(application=application_node("a-1"))
        found = applications.get_application(client, "a-1")
        assert found is not None and found.id == "a-1"

    def test_missing_returns_none(self):
        assert (
            applications.get_application(FakeUpworkClient(application={}), "x") is None
        )

    def test_api_error_raises(self):
        client = FakeUpworkClient(application=RuntimeError("gone"))
        with pytest.raises(applications.ApplicationsError, match="fetch application"):
            applications.get_application(client, "a-1")


class TestOffers:
    def test_list_unwraps_and_drops_idless_offers(self):
        client = FakeUpworkClient(
            offers=connection(offer_node("o-1"), {"title": "no id here"})
        )
        found = applications.list_offers(client)
        assert [o.id for o in found] == ["o-1"]

    def test_state_filter_reaches_the_client(self):
        client = FakeUpworkClient()
        applications.list_offers(client, state="ACTIVE", limit=7)
        assert client.offer_queries == [{"limit": 7, "state": "ACTIVE"}]

    def test_get_offer(self):
        client = FakeUpworkClient(offer=offer_node("o-9", title="Backend work"))
        offer = applications.get_offer(client, "o-9")
        assert offer is not None and offer.title == "Backend work"

    def test_get_offer_missing_returns_none(self):
        assert applications.get_offer(FakeUpworkClient(offer={}), "x") is None

    def test_offers_for_application(self):
        client = FakeUpworkClient(offers_for_application=[offer_node("o-2")])
        assert [o.id for o in applications.offers_for_application(client, "a-1")] == [
            "o-2"
        ]

    def test_withdraw_reaches_the_client(self):
        client = FakeUpworkClient()
        applications.withdraw_offer(client, "o-1", "OTHER", "changed my mind")
        assert client.withdrawn == [("o-1", "OTHER", "changed my mind")]

    def test_withdraw_sends_none_for_an_empty_message(self):
        client = FakeUpworkClient()
        applications.withdraw_offer(client, "o-1", "OTHER", "")
        assert client.withdrawn == [("o-1", "OTHER", None)]

    def test_list_api_error_raises(self):
        client = FakeUpworkClient(offers=RuntimeError("nope"))
        with pytest.raises(applications.ApplicationsError, match="fetch offers"):
            applications.list_offers(client)


class TestOfferTerms:
    def test_fixed_price(self):
        offer = Offer.from_api(offer_node(budget="5000"))
        assert offer.terms == OfferTerms(amount=5000.0, currency="USD", is_fixed=True)

    def test_hourly_with_a_weekly_cap(self):
        offer = Offer.from_api(
            offer_node(budget=None, hourly_rate="85", weekly_limit=30)
        )
        assert offer.terms.amount == 85.0
        assert offer.terms.weekly_hours_limit == 30
        assert offer.terms.is_fixed is False

    def test_hourly_without_a_cap(self):
        offer = Offer.from_api(offer_node(budget=None, hourly_rate="85"))
        assert offer.terms.weekly_hours_limit is None

    def test_no_terms(self):
        offer = Offer.from_api(offer_node(budget=None))
        assert offer.terms.amount is None

    def test_dates_survive_either_branch(self):
        node = offer_node(budget="100")
        node["offerTerms"]["expectedStartDate"] = "2026-10-01"
        node["offerTerms"]["expectedEndDate"] = "2026-12-01"
        terms = Offer.from_api(node).terms
        assert (terms.start_date, terms.end_date) == ("2026-10-01", "2026-12-01")


class TestApplicationModel:
    def test_job_is_a_job_posting(self):
        """The nested posting reuses JobPosting.from_graphql rather than a
        second parser."""
        application = Application.from_api(application_node(job_title="Build an API"))
        assert application.job is not None
        assert application.job.title == "Build an API"
        assert application.job.budget_amount == 3000.0

    def test_application_without_a_posting(self):
        application = Application.from_api({"id": "a-1"})
        assert application.job is None
        assert application.job_title == ""

    def test_cover_letter_fallback_key(self):
        application = Application.from_api({"id": "a", "coverLetter": "Hi"})
        assert application.cover_letter == "Hi"

    def test_sort_key_falls_back_when_a_stamp_is_missing(self):
        application = Application.from_api(
            {"id": "a", "auditDetails": {"createdDateTime": "2026-01-01"}}
        )
        assert application.sort_key("modified") == "2026-01-01"
        # "status" ordering deliberately does not fall back to created,
        # matching the behaviour this replaced.
        assert application.sort_key("status") == ""


class TestRemainingErrorPaths:
    def test_offers_for_application_error_raises(self):
        client = FakeUpworkClient(offers_for_application=RuntimeError("nope"))
        with pytest.raises(
            applications.ApplicationsError, match="offers for application"
        ):
            applications.offers_for_application(client, "a-1")

    def test_get_offer_error_raises(self):
        client = FakeUpworkClient(offer=RuntimeError("gone"))
        with pytest.raises(applications.ApplicationsError, match="fetch offer"):
            applications.get_offer(client, "o-1")

    def test_withdraw_error_raises(self):
        client = FakeUpworkClient(offer=RuntimeError("refused"))
        with pytest.raises(applications.ApplicationsError, match="withdraw offer"):
            applications.withdraw_offer(client, "o-1", "Other")
