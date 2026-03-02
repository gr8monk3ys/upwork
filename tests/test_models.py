"""Tests for data models in upwork_cli.models."""

import pytest

from upwork_cli.models import JobPosting, Contract, Message
from tests.conftest import _make_graphql_node, _make_rest_job, _make_rss_entry


class TestJobPostingFromGraphQL:
    def test_full_data(self, sample_graphql_node):
        job = JobPosting.from_graphql(sample_graphql_node)
        assert job.id == "~01abc123"
        assert job.title == "Python Developer Needed"
        assert job.skills == ["Python", "FastAPI"]
        assert job.budget_amount == 5000.0
        assert job.client_country == "United States"
        assert job.client_total_spent == 150000.0
        assert job.client_verified is True
        assert job.category == "Web Development"
        assert job.subcategory == "Backend Development"

    def test_missing_optionals(self):
        node = {"id": "~01min", "title": "Minimal Job"}
        job = JobPosting.from_graphql(node)
        assert job.id == "~01min"
        assert job.budget_amount is None
        assert job.client_country == ""
        assert job.client_verified is False
        assert job.category == ""


class TestJobPostingFromRest:
    def test_full_data(self, sample_rest_job):
        job = JobPosting.from_rest(sample_rest_job)
        assert job.id == "~01rest456"
        assert job.title == "Frontend React Dev"
        assert job.skills == ["React", "TypeScript"]
        assert job.budget_amount == 3000.0
        assert job.client_country == "Canada"

    def test_missing_optionals(self):
        data = {"id": "~01bare", "title": "Bare Job"}
        job = JobPosting.from_rest(data)
        assert job.id == "~01bare"
        assert job.budget_amount is None
        assert job.skills == []


class TestJobPostingFromRss:
    def test_full_data(self, sample_rss_entry):
        job = JobPosting.from_rss(sample_rss_entry)
        # from_rss splits link on "~" and takes the last segment
        assert job.id == "01rss789"
        assert job.title == "Data Analyst Needed"
        assert job.budget_amount == 2500.0

    def test_no_budget_in_rss(self):
        entry = {"title": "No Budget Job", "link": "", "id": "rss-no-budget", "summary": "Just text."}
        job = JobPosting.from_rss(entry)
        assert job.budget_amount is None


class TestToDbDict:
    def test_roundtrip_fields(self, sample_graphql_node):
        job = JobPosting.from_graphql(sample_graphql_node)
        d = job.to_db_dict()
        assert d["id"] == job.id
        assert d["title"] == job.title
        assert d["skills"] == job.skills
        assert d["budget_amount"] == job.budget_amount
        assert d["client_country"] == job.client_country

    def test_contains_expected_keys(self):
        job = JobPosting(id="~01x", title="Test")
        d = job.to_db_dict()
        expected_keys = {
            "id", "title", "description", "skills", "budget_amount",
            "budget_currency", "duration", "engagement", "client_country",
            "client_total_spent", "client_total_hires", "client_feedback",
            "created_at", "category", "subcategory",
        }
        assert set(d.keys()) == expected_keys


class TestSummaryForAi:
    def test_includes_title(self):
        job = JobPosting(id="~01x", title="Python Dev")
        summary = job.summary_for_ai()
        assert "Title: Python Dev" in summary

    def test_includes_all_set_fields(self, sample_graphql_node):
        job = JobPosting.from_graphql(sample_graphql_node)
        summary = job.summary_for_ai()
        assert "Title:" in summary
        assert "Skills:" in summary
        assert "Budget:" in summary
        assert "Client Country:" in summary
        assert "Payment Verified" in summary


class TestContract:
    def test_from_api(self):
        data = {
            "reference": "c-123",
            "job": {"title": "Web Dev Contract"},
            "status": "active",
            "created_time": "2025-01-01",
            "buyer": {"company_name": "Acme Corp"},
            "hourly_charge_rate": {"amount": 75.0},
            "hours_per_week": 40.0,
            "total_charge": {"amount": 5000.0},
        }
        c = Contract.from_api(data)
        assert c.id == "c-123"
        assert c.title == "Web Dev Contract"
        assert c.hourly_rate == 75.0


class TestMessage:
    def test_from_api(self):
        data = {
            "id": "msg-1",
            "userId": "user-42",
            "message": "Hello!",
            "createdAt": "2025-01-15T10:00:00Z",
        }
        m = Message.from_api(data, room_id="room-1")
        assert m.id == "msg-1"
        assert m.sender == "user-42"
        assert m.content == "Hello!"
        assert m.room_id == "room-1"
