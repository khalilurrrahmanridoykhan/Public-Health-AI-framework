"""Deterministic public-health reporting period utilities."""

from __future__ import annotations

from datetime import date, timedelta
import calendar
import re


def resolve_period(value: str) -> tuple[date, date]:
    """Resolve an ISO week, calendar month, or quarter to inclusive dates."""
    week = re.fullmatch(r"(\d{4})-W(\d{2})", value)
    if week:
        try:
            start = date.fromisocalendar(int(week.group(1)), int(week.group(2)), 1)
        except ValueError as error:
            raise ValueError(f"Invalid epidemiological week '{value}'.") from error
        return start, start + timedelta(days=6)

    month = re.fullmatch(r"(\d{4})-(\d{2})", value)
    if month:
        year, month_number = map(int, month.groups())
        if not 1 <= month_number <= 12:
            raise ValueError(f"Invalid calendar month '{value}'.")
        return date(year, month_number, 1), date(year, month_number, calendar.monthrange(year, month_number)[1])

    quarter = re.fullmatch(r"(\d{4})-Q([1-4])", value)
    if quarter:
        year, quarter_number = map(int, quarter.groups())
        first_month = (quarter_number - 1) * 3 + 1
        last_month = first_month + 2
        return date(year, first_month, 1), date(year, last_month, calendar.monthrange(year, last_month)[1])

    raise ValueError("Period must use YYYY-Www, YYYY-MM, or YYYY-Qn format.")
