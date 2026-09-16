"""Tests for upwork_cli.jobs.

The GraphQL unwrapping and the seen-dedup used to sit inside command
helpers that no test could reach, because commands/jobs.py constructed its
own client and offered nothing to substitute.
"""

import pytest

from tests.fakes import FakeUpworkClient, job_node, job_search_payload
from upwork_cli import jobs
from upwork_cli.db import get_connection, init_db, is_seen
from upwork_cli.models import JobPosting


class TestSearch:
    def test_unwraps_the_marketplace_payload(self):
        client = FakeUpworkClient(
            search_results=job_search_payload(
                job_node("~01a", title="Build an API", amount="5000")
            )
        )
        found = jobs.search(client, "python")
        assert [j.id for j in found] == ["~01a"]
        assert found[0].title == "Build an API"
        assert found[0].budget_amount == 5000.0
        assert found[0].skills == ["Python", "FastAPI"]

    def test_passes_the_query_and_limit_through(self):
        client = FakeUpworkClient()
        jobs.search(client, "fastapi", limit=7)
        assert client.searches == [("fastapi", 7)]

    def test_no_results(self):
        assert jobs.search(FakeUpworkClient(), "nothing") == []

    def test_edges_without_a_node_are_skipped(self):
        client = FakeUpworkClient(
            search_results={
                "data": {
                    "marketplaceJobPostings": {"edges": [{}, {"node": job_node()}]}
                }
            }
        )
        assert len(jobs.search(client, "q")) == 1

    def test_missing_data_key(self):
        assert jobs.search(FakeUpworkClient(search_results={}), "q") == []

    def test_api_error_raises(self):
        client = FakeUpworkClient(search_results=RuntimeError("upstream"))
        with pytest.raises(jobs.JobsError, match="API search failed"):
            jobs.search(client, "q")


class TestGetDetail:
    def test_returns_a_posting(self):
        client = FakeUpworkClient(
            job_detail={"id": "~01a", "title": "Fresh", "snippet": "From the API."}
        )
        job = jobs.get_detail(client, "~01a")
        assert job is not None
        assert job.title == "Fresh"
        assert job.description == "From the API."

    def test_missing_returns_none(self):
        assert jobs.get_detail(FakeUpworkClient(job_detail={}), "~01a") is None

    def test_api_error_raises(self):
        client = FakeUpworkClient(job_detail=RuntimeError("gone"))
        with pytest.raises(jobs.JobsError, match="API lookup failed"):
            jobs.get_detail(client, "~01a")


class TestCache:
    def test_stores_and_places_in_the_pipeline(self, isolated_config):
        init_db()
        jobs.cache([JobPosting(id="~01a", title="Cached")])

        with get_connection() as conn:
            assert (
                conn.execute(
                    "SELECT title FROM jobs WHERE id = ?", ("~01a",)
                ).fetchone()["title"]
                == "Cached"
            )
            assert (
                conn.execute(
                    "SELECT stage FROM pipeline WHERE job_id = ?", ("~01a",)
                ).fetchone()["stage"]
                == "found"
            )

    def test_does_not_move_a_job_already_further_along(self, isolated_config):
        init_db()
        jobs.cache([JobPosting(id="~01a", title="Cached")])
        with get_connection() as conn:
            conn.execute(
                "UPDATE pipeline SET stage = 'applied' WHERE job_id = ?", ("~01a",)
            )

        jobs.cache([JobPosting(id="~01a", title="Cached again")])
        with get_connection() as conn:
            stage = conn.execute(
                "SELECT stage FROM pipeline WHERE job_id = ?", ("~01a",)
            ).fetchone()["stage"]
        assert stage == "applied"


class TestCollectNew:
    def test_first_sighting_is_new_and_recorded(self, isolated_config):
        init_db()
        found = jobs.collect_new([JobPosting(id="~01a", title="A")], "python")
        assert [j.id for j in found] == ["~01a"]
        assert is_seen("~01a")

    def test_second_sighting_is_not_new(self, isolated_config):
        init_db()
        jobs.collect_new([JobPosting(id="~01a", title="A")], "python")
        assert jobs.collect_new([JobPosting(id="~01a", title="A")], "python") == []

    def test_seen_is_per_job_not_per_search_term(self, isolated_config):
        """A job surfaced by one saved search is not new again under another."""
        init_db()
        jobs.collect_new([JobPosting(id="~01a", title="A")], "python")
        assert jobs.collect_new([JobPosting(id="~01a", title="A")], "fastapi") == []

    def test_mixes_new_and_seen(self, isolated_config):
        init_db()
        jobs.collect_new([JobPosting(id="~01a", title="A")], "python")
        found = jobs.collect_new(
            [JobPosting(id="~01a", title="A"), JobPosting(id="~01b", title="B")],
            "python",
        )
        assert [j.id for j in found] == ["~01b"]
