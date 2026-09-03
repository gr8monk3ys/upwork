"""Tests for helper functions in upwork_cli.commands.jobs."""

from datetime import datetime, timedelta, timezone

from upwork_cli.commands.jobs import (
    _filter_jobs,
    _format_skills,
    _get_saved_search_terms,
    _normalize_search_term,
    _score_color,
)
from upwork_cli.config import Settings
from upwork_cli.models import JobPosting


class TestFormatSkills:
    def test_empty_skills(self):
        assert _format_skills([]) == ""
        assert _format_skills(None) == ""

    def test_few_skills(self):
        assert _format_skills(["Python", "Django"]) == "Python, Django"

    def test_many_skills_truncated(self):
        skills = ["Python", "Django", "React", "PostgreSQL", "Docker"]
        result = _format_skills(skills, max_count=3)
        assert "Python" in result
        assert "+2" in result

    def test_json_string_skills(self):
        skills_str = '["Go", "Rust", "Zig"]'
        result = _format_skills(skills_str, max_count=2)
        assert "Go" in result
        assert "+1" in result


class TestScoreColor:
    def test_high_score_green(self):
        assert _score_color(8) == "green"
        assert _score_color(10) == "green"

    def test_mid_score_yellow(self):
        assert _score_color(5) == "yellow"
        assert _score_color(7) == "yellow"

    def test_low_score_red(self):
        assert _score_color(1) == "red"
        assert _score_color(4) == "red"


class TestFilterJobs:
    def _make_posting(self, budget=None, **kw):
        return JobPosting(id="~01x", title="Test", budget_amount=budget, **kw)

    def test_no_filters(self):
        jobs = [self._make_posting(budget=100), self._make_posting(budget=200)]
        assert len(_filter_jobs(jobs, None, None, None, None)) == 2

    def test_budget_min_filter(self):
        jobs = [self._make_posting(budget=100), self._make_posting(budget=500)]
        filtered = _filter_jobs(
            jobs, budget_min=200, budget_max=None, job_type=None, posted=None
        )
        assert len(filtered) == 1
        assert filtered[0].budget_amount == 500

    def test_budget_max_filter(self):
        jobs = [self._make_posting(budget=100), self._make_posting(budget=500)]
        filtered = _filter_jobs(
            jobs, budget_min=None, budget_max=200, job_type=None, posted=None
        )
        assert len(filtered) == 1
        assert filtered[0].budget_amount == 100

    def test_none_budget_excluded_with_min(self):
        jobs = [self._make_posting(budget=None)]
        filtered = _filter_jobs(
            jobs, budget_min=50, budget_max=None, job_type=None, posted=None
        )
        assert len(filtered) == 0

    def test_job_type_filter(self):
        jobs = [
            self._make_posting(budget=100, engagement="Hourly: 30+ hrs/week"),
            self._make_posting(budget=200, engagement="Fixed-price"),
        ]
        filtered = _filter_jobs(
            jobs, budget_min=None, budget_max=None, job_type="fixed", posted=None
        )
        assert len(filtered) == 1
        assert filtered[0].engagement == "Fixed-price"

    def test_posted_filter(self):
        now = datetime.now(timezone.utc)
        jobs = [
            self._make_posting(
                budget=100, created_at=(now - timedelta(hours=2)).isoformat()
            ),
            self._make_posting(
                budget=200, created_at=(now - timedelta(days=2)).isoformat()
            ),
        ]
        filtered = _filter_jobs(
            jobs, budget_min=None, budget_max=None, job_type=None, posted="24h"
        )
        assert len(filtered) == 1
        assert filtered[0].budget_amount == 100


class TestSavedSearchHelpers:
    def test_normalize_search_term(self):
        assert _normalize_search_term("  python   developer  ") == "python developer"

    def test_saved_search_terms_are_deduplicated(self):
        settings = Settings(
            default_search_terms=[
                " python developer ",
                "python developer",
                "react native",
            ]
        )
        assert _get_saved_search_terms(settings) == ["python developer", "react native"]
