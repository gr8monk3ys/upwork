"""Tests for upwork_cli.output.

These cover the decisions that used to be made separately in each command
module: how money reads, what "nothing found" does to the exit code, and
what a failure does to it.
"""

import pytest

from upwork_cli import output


class TestMoney:
    def test_two_decimals_and_currency(self):
        assert output.money(1234.56) == "$1,234.56 USD"

    def test_keeps_the_cents(self):
        """jobs' formatter rounded: 2500.99 used to print as "$2,501 USD"."""
        assert output.money(2500.99) == "$2,500.99 USD"

    def test_whole_amounts_still_show_cents(self):
        assert output.money(5000) == "$5,000.00 USD"

    def test_other_currencies(self):
        assert output.money(1000, "EUR") == "$1,000.00 EUR"

    def test_none_is_not_available(self):
        assert output.money(None) == "N/A"

    def test_zero_is_a_real_amount(self):
        assert output.money(0) == "$0.00 USD"


class TestTruncate:
    def test_short_string_unchanged(self):
        assert output.truncate("hello", 10) == "hello"

    def test_exact_length_unchanged(self):
        assert output.truncate("hello", 5) == "hello"

    def test_long_string_truncated(self):
        result = output.truncate("hello world", 8)
        assert result == "hello..."
        assert len(result) == 8

    def test_empty_string(self):
        assert output.truncate("", 5) == ""

    def test_none_is_tolerated(self):
        assert output.truncate(None, 5) == ""


class TestFailAndEmpty:
    def test_fail_exits_one(self, capsys):
        with pytest.raises(SystemExit) as excinfo:
            output.fail("something broke")
        assert excinfo.value.code == 1
        assert "something broke" in capsys.readouterr().out

    def test_fail_accepts_an_exception(self, capsys):
        with pytest.raises(SystemExit):
            output.fail(RuntimeError("upstream is down"))
        assert "upstream is down" in capsys.readouterr().out

    def test_empty_does_not_exit(self, capsys):
        output.empty("No jobs found.")
        assert "No jobs found." in capsys.readouterr().out
