"""Tests for the _parse_markdown_profile() function in commands/config.py."""

from datetime import datetime, timezone

from upwork_cli.commands.config import _parse_markdown_profile


class TestTitleParsing:
    def test_basic_title(self):
        md = "## Professional Title\nSenior Python Developer"
        result = _parse_markdown_profile(md)
        assert result["title"] == "Senior Python Developer"

    def test_bold_title_stripped(self):
        md = "## Professional Title\n**Senior Python Developer**"
        result = _parse_markdown_profile(md)
        assert result["title"] == "Senior Python Developer"

    def test_title_with_horizontal_rule(self):
        md = "## Professional Title\n---\nSenior Dev\n---"
        result = _parse_markdown_profile(md)
        assert result["title"] == "Senior Dev"

    def test_fallback_title_heading(self):
        md = "## Title\nBackend Engineer"
        result = _parse_markdown_profile(md)
        assert result["title"] == "Backend Engineer"


class TestOverviewParsing:
    def test_basic_overview(self):
        md = "## Professional Overview\nI build REST APIs with FastAPI and Django."
        result = _parse_markdown_profile(md)
        assert "REST APIs" in result["overview"]

    def test_overview_with_trailing_rule(self):
        md = "## Professional Overview\nI build things.\n---"
        result = _parse_markdown_profile(md)
        assert result["overview"] == "I build things."


class TestSkillsParsing:
    def test_bullet_list_skills(self):
        md = "## Skills to Add\n- Python\n- FastAPI\n- PostgreSQL"
        result = _parse_markdown_profile(md)
        assert result["skills"] == ["Python", "FastAPI", "PostgreSQL"]

    def test_comma_separated_skills(self):
        md = "## Skills to Add\nPython, FastAPI, PostgreSQL"
        result = _parse_markdown_profile(md)
        assert result["skills"] == ["Python", "FastAPI", "PostgreSQL"]

    def test_skills_with_subheadings_skipped(self):
        md = "## Skills to Add\n### Programming\n- Python\n- Go\n### Databases\n- PostgreSQL"
        result = _parse_markdown_profile(md)
        assert "Python" in result["skills"]
        assert "Go" in result["skills"]
        assert "PostgreSQL" in result["skills"]
        # Subheading text should NOT be in the skills list
        assert "Programming" not in result["skills"]

    def test_fallback_skills_heading(self):
        md = "## Skills\n- Docker\n- Kubernetes"
        result = _parse_markdown_profile(md)
        assert result["skills"] == ["Docker", "Kubernetes"]


class TestPortfolioParsing:
    def test_portfolio_entries_heading(self):
        md = (
            "## Portfolio Entries\n"
            "### My Project\nA cool project.\n"
            "### Other Project\nAnother thing."
        )
        result = _parse_markdown_profile(md)
        assert len(result["portfolio"]) == 2
        assert result["portfolio"][0]["name"] == "My Project"

    def test_portfolio_heading_variant(self):
        md = "## Portfolio\n### App One\nBuilt an app."
        result = _parse_markdown_profile(md)
        assert len(result["portfolio"]) == 1
        assert result["portfolio"][0]["name"] == "App One"

    def test_bold_portfolio_names(self):
        md = "## Portfolio Entries\n**My Project**\nA cool project."
        result = _parse_markdown_profile(md)
        assert result["portfolio"][0]["name"] == "My Project"


class TestRateAndExperience:
    def test_hourly_rate_extraction(self):
        md = "## Hourly Rate Suggestion\n$75-$100/hr"
        result = _parse_markdown_profile(md)
        assert "$75-$100/hr" in result["hourly_rate"]

    def test_experience_years_from_overview(self):
        md = "## Professional Overview\nI have 8+ years of experience in software."
        result = _parse_markdown_profile(md)
        assert result["experience_years"] == 8

    def test_experience_years_from_employment_history(self):
        current_year = datetime.now(timezone.utc).year
        md = "## Employment History\nSenior Dev at Acme Corp (2017 - Present)"
        result = _parse_markdown_profile(md)
        assert result["experience_years"] == current_year - 2017


class TestEdgeCases:
    def test_empty_input(self):
        result = _parse_markdown_profile("")
        assert result == {}

    def test_no_recognized_headings(self):
        md = "## Random Heading\nSome text."
        result = _parse_markdown_profile(md)
        assert "title" not in result

    def test_real_draft_file_has_parseable_structure(self, tmp_path):
        """Regression test: a realistic markdown profile should parse without error."""
        md = (
            "## Professional Title\n**Full-Stack Python Developer**\n\n"
            "## Professional Overview\n"
            "I'm a developer with 10+ years building web apps.\n\n"
            "## Skills to Add\n- Python\n- Django\n- React\n- PostgreSQL\n\n"
            "## Hourly Rate Suggestion\n$60-$90/hr\n\n"
            "## Portfolio Entries\n"
            "### SaaS Dashboard\nBuilt a real-time dashboard.\n"
            "### API Gateway\nDesigned a gateway for microservices.\n"
        )
        result = _parse_markdown_profile(md)
        assert result["title"] == "Full-Stack Python Developer"
        assert result["experience_years"] == 10
        assert len(result["skills"]) == 4
        assert len(result["portfolio"]) == 2
        assert "$60-$90/hr" in result["hourly_rate"]
