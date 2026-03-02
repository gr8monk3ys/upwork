"""Tests for helper functions in upwork_cli.commands.jobs."""

import json

import pytest

from upwork_cli.commands.jobs import (
    _truncate,
    _format_budget,
    _format_skills,
    _score_color,
    _filter_jobs,
)
from upwork_cli.models import JobPosting


class TestTruncate:
    def test_short_string_unchanged(self):
        assert _truncate("hello", 10) == "hello"

    def test_exact_length_unchanged(self):
        assert _truncate("hello", 5) == "hello"

    def test_long_string_truncated(self):
        result = _truncate("hello world", 8)
        assert result == "hello..."
        assert len(result) == 8

    def test_empty_string(self):
        assert _truncate("", 5) == ""


class TestFormatBudget:
    def test_none_budget(self):
        assert _format_budget(None) == "N/A"

    def test_integer_budget(self):
        assert _format_budget(5000) == "$5,000 USD"

    def test_float_budget(self):
        assert _format_budget(2500.99) == "$2,501 USD"

    def test_custom_currency(self):
        assert _format_budget(1000, "EUR") == "$1,000 EUR"


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
        filtered = _filter_jobs(jobs, budget_min=200, budget_max=None, job_type=None, posted=None)
        assert len(filtered) == 1
        assert filtered[0].budget_amount == 500

    def test_budget_max_filter(self):
        jobs = [self._make_posting(budget=100), self._make_posting(budget=500)]
        filtered = _filter_jobs(jobs, budget_min=None, budget_max=200, job_type=None, posted=None)
        assert len(filtered) == 1
        assert filtered[0].budget_amount == 100

    def test_none_budget_excluded_with_min(self):
        jobs = [self._make_posting(budget=None)]
        filtered = _filter_jobs(jobs, budget_min=50, budget_max=None, job_type=None, posted=None)
        assert len(filtered) == 0
