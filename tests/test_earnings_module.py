"""Tests for upwork_cli.earnings.

The row normalisation and the month/week bucketing used to live inside the
summary command body, where nothing exercised them directly. They are tested
here through the module's interface, with the clock passed in.
"""

from datetime import datetime

import pytest

from tests.fakes import (
    FakeUpworkClient,
    earning_cells,
    earning_flat,
    earnings_payload,
)
from upwork_cli import earnings
from upwork_cli.models import EarningRow


class TestFreelancerReference:
    def test_nested_info_ref(self):
        client = FakeUpworkClient(user_info={"info": {"ref": "~free1"}})
        earnings.fetch(client)
        assert client.earnings_params == [(None, None)]

    def test_falls_back_to_top_level_keys(self):
        client = FakeUpworkClient(user_info={"id": "alt-ref"})
        rows, _ = earnings.fetch(client)
        assert rows == []

    def test_missing_reference_raises(self):
        client = FakeUpworkClient(user_info={})
        with pytest.raises(earnings.EarningsError, match="freelancer reference"):
            earnings.fetch(client)

    def test_api_error_raises(self):
        client = FakeUpworkClient(user_info=RuntimeError("down"))
        with pytest.raises(earnings.EarningsError, match="user info"):
            earnings.fetch(client)


class TestRowShapes:
    def test_cell_array_shape(self):
        row = EarningRow.from_api(
            earning_cells(date="2026-09-01", client="Acme", amount="1200.00")
        )
        assert row.date == "2026-09-01"
        assert row.client == "Acme"
        assert row.amount == 1200.0

    def test_flat_dict_shape(self):
        row = EarningRow.from_api(
            earning_flat(date="2026-08-02", client="Beta", amount="99.5")
        )
        assert row.date == "2026-08-02"
        assert row.client == "Beta"
        assert row.amount == 99.5

    def test_bare_list_shape(self):
        row = EarningRow.from_api(["2026-07-03", "Gamma", "Job", "50", "Hourly"])
        assert row.date == "2026-07-03"
        assert row.client == "Gamma"
        assert row.amount == 50.0
        assert row.kind == "Hourly"

    def test_short_list_does_not_raise(self):
        assert EarningRow.from_api(["2026-07-03"]).amount == 0.0

    def test_unparseable_amount_becomes_zero(self):
        assert EarningRow.from_api(earning_flat(amount="n/a")).amount == 0.0

    def test_unknown_shape_is_empty(self):
        assert EarningRow.from_api("nonsense") == EarningRow()

    def test_all_three_shapes_agree(self):
        """The same earning, however it arrives, becomes the same row."""
        cells = EarningRow.from_api(earning_cells())
        flat = EarningRow.from_api(earning_flat())
        assert cells == flat


class TestFetch:
    def test_reads_rows_from_the_table_key(self):
        client = FakeUpworkClient(earnings=earnings_payload(earning_cells()))
        rows, _ = earnings.fetch(client)
        assert len(rows) == 1

    def test_reads_rows_from_the_rows_key(self):
        client = FakeUpworkClient(earnings={"rows": [earning_flat()]})
        assert len(earnings.fetch(client)[0]) == 1

    def test_reads_rows_from_the_earnings_key(self):
        client = FakeUpworkClient(earnings={"earnings": [earning_flat()]})
        assert len(earnings.fetch(client)[0]) == 1

    def test_no_rows(self):
        assert earnings.fetch(FakeUpworkClient())[0] == []

    def test_date_filter_is_sent(self):
        client = FakeUpworkClient()
        earnings.fetch(client, "2026-01-01", "2026-06-30")
        assert client.earnings_params == [("2026-01-01", "2026-06-30")]

    def test_single_sided_filter(self):
        client = FakeUpworkClient()
        earnings.fetch(client, "2026-01-01", None)
        assert client.earnings_params == [("2026-01-01", None)]

    def test_no_filter_sends_no_dates(self):
        client = FakeUpworkClient()
        earnings.fetch(client)
        assert client.earnings_params == [(None, None)]

    def test_api_error_raises(self):
        client = FakeUpworkClient(earnings=RuntimeError("boom"))
        with pytest.raises(earnings.EarningsError, match="fetch earnings"):
            earnings.fetch(client)


class TestColumnNames:
    def test_uses_the_reports_own_labels(self):
        payload = earnings_payload(cols=["When", "Who", "What", "How much", "Kind"])
        assert earnings.column_names(payload)[0] == "When"

    def test_falls_back_to_the_standard_five(self):
        assert earnings.column_names({}) == list(EarningRow.COLUMNS)


class TestSummarise:
    #: A Friday, so this week starts Monday 2026-08-31. Naive on purpose:
    #: summarise() compares against naive dates parsed from the report.
    NOW = datetime(2026, 9, 4, 12, 0, 0)  # noqa: DTZ001

    def _rows(self, *pairs):
        return [EarningRow(date=d, amount=a) for d, a in pairs]

    def test_totals_everything(self):
        rows = self._rows(("2024-01-01", 100.0), ("2026-09-03", 50.0))
        assert earnings.summarise(rows, self.NOW).total == 150.0

    def test_this_month_excludes_last_month(self):
        rows = self._rows(("2026-08-31", 100.0), ("2026-09-01", 25.0))
        assert earnings.summarise(rows, self.NOW).this_month == 25.0

    def test_this_week_starts_on_monday(self):
        rows = self._rows(
            ("2026-08-30", 10.0),  # Sunday, previous week
            ("2026-08-31", 20.0),  # Monday, this week
            ("2026-09-04", 30.0),  # today
        )
        summary = earnings.summarise(rows, datetime(2026, 9, 4, 12))  # noqa: DTZ001
        assert summary.this_week == 50.0

    def test_month_boundary_is_inclusive(self):
        rows = self._rows(("2026-09-01", 40.0))
        assert earnings.summarise(rows, self.NOW).this_month == 40.0

    def test_undated_rows_count_to_the_total_only(self):
        rows = self._rows(("", 70.0))
        summary = earnings.summarise(rows, self.NOW)
        assert summary.total == 70.0
        assert summary.this_month == 0.0
        assert summary.this_week == 0.0

    @pytest.mark.parametrize(
        "value", ["2026-09-03", "2026-09-03T09:30:00", "09/03/2026", "20260903"]
    )
    def test_every_supported_date_format(self, value):
        rows = self._rows((value, 10.0))
        assert earnings.summarise(rows, self.NOW).this_month == 10.0

    def test_no_rows(self):
        summary = earnings.summarise([], self.NOW)
        assert (summary.total, summary.this_month, summary.this_week) == (0.0, 0.0, 0.0)
