from __future__ import annotations

from datetime import date

import pytest

from app.projects.duration import (
    ProjectDateRangeInvalid,
    compare_imported_duration,
    derive_project_duration,
)


@pytest.mark.parametrize(
    ("start", "end", "months"),
    [
        (date(2027, 3, 1), date(2028, 8, 31), 18),
        (date(2027, 3, 1), date(2027, 3, 31), 1),
        (date(2027, 12, 1), date(2028, 1, 31), 2),
        (date(2028, 2, 1), date(2028, 2, 29), 1),
    ],
)
def test_full_calendar_months_are_inclusive(start, end, months):
    result = derive_project_duration(start, end)
    assert result.duration_months == months
    assert result.status == "derived"
    assert result.reason_code == "duration_derived"


@pytest.mark.parametrize(
    ("start", "end"),
    [(None, None), (date(2027, 1, 1), None), (None, date(2027, 1, 31))],
)
def test_missing_date_is_not_derivable(start, end):
    result = derive_project_duration(start, end)
    assert result.duration_months is None
    assert result.status == "not_derivable"
    assert result.reason_code == "duration_dates_missing"


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (date(2027, 1, 2), date(2027, 1, 31)),
        (date(2027, 1, 1), date(2027, 2, 27)),
    ],
)
def test_partial_months_require_review_without_rounding(start, end):
    result = derive_project_duration(start, end)
    assert result.duration_months is None
    assert result.status == "review_required"
    assert result.reason_code == "duration_boundary_conflict"


def test_reverse_range_is_invalid():
    with pytest.raises(ProjectDateRangeInvalid):
        derive_project_duration(date(2027, 2, 1), date(2027, 1, 31))


def test_imported_duration_is_comparison_only():
    assert (
        compare_imported_duration(
            date(2027, 3, 1), date(2028, 8, 31), 18
        )
        == "duration_match"
    )
    assert (
        compare_imported_duration(
            date(2027, 3, 1), date(2028, 8, 31), 17
        )
        == "duration_conflict"
    )
