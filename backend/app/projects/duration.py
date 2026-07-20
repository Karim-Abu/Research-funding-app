"""Single source of truth for the project duration.

The persisted ``projects.duration_months`` column is legacy compatibility
storage only.  Product code must derive the duration from the date range via
this module and must never round partial calendar months.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from typing import Literal

DurationStatus = Literal["derived", "not_derivable", "review_required"]
DurationReasonCode = Literal[
    "duration_derived",
    "duration_dates_missing",
    "duration_boundary_conflict",
]


class ProjectDateRangeInvalid(ValueError):
    """Raised when the project ends before it starts."""


@dataclass(frozen=True, slots=True)
class ProjectDuration:
    duration_months: int | None
    status: DurationStatus
    reason_code: DurationReasonCode


def derive_project_duration(
    start_date: date | None, end_date: date | None
) -> ProjectDuration:
    """Derive fully covered calendar months, including both edge months."""
    if start_date is None or end_date is None:
        return ProjectDuration(None, "not_derivable", "duration_dates_missing")
    if end_date < start_date:
        raise ProjectDateRangeInvalid("Project end date is before its start date.")
    end_is_month_end = end_date.day == calendar.monthrange(
        end_date.year, end_date.month
    )[1]
    if start_date.day != 1 or not end_is_month_end:
        return ProjectDuration(
            None, "review_required", "duration_boundary_conflict"
        )
    months = (end_date.year - start_date.year) * 12 + end_date.month - start_date.month + 1
    return ProjectDuration(months, "derived", "duration_derived")


def compare_imported_duration(
    start_date: date | None,
    end_date: date | None,
    imported_months: int | None,
) -> Literal[
    "duration_match",
    "duration_conflict",
    "not_derivable",
    "duration_boundary_conflict",
]:
    """Compare a raw PDF candidate without making it an editable truth."""
    result = derive_project_duration(start_date, end_date)
    if result.status == "not_derivable":
        return "not_derivable"
    if result.status == "review_required":
        return "duration_boundary_conflict"
    return (
        "duration_match"
        if imported_months == result.duration_months
        else "duration_conflict"
    )
