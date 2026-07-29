"""Helpers for validating and building Life Events NG event data."""
from __future__ import annotations

import re
import uuid
from datetime import date
from typing import Any

from .const import (
    CONF_EVENT_CUSTOM_LABEL,
    CONF_EVENT_DATE,
    CONF_EVENT_ICON,
    CONF_EVENT_NAME,
    CONF_EVENT_TYPE,
    CONF_EVENT_YEAR_UNKNOWN,
    EVENT_TYPES,
)


class EventValidationError(ValueError):
    """Raised when event data is invalid."""

    def __init__(self, field: str, message: str) -> None:
        """Initialize the validation error."""
        super().__init__(message)
        self.field = field


def normalize_event_date(
    date_str: str,
    year_unknown: bool | None = None,
) -> tuple[str, bool]:
    """Normalize an event date and return the normalized date plus year flag.

    Accepts YYYY-M-D, YYYY-MM-D, YYYY-M-DD, YYYY-MM-DD when the year is known,
    and M-D, MM-D, M-DD, MM-DD when the year is unknown.
    """
    date_str = date_str.strip()

    if year_unknown is not True:
        m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", date_str)
        if m:
            year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
            try:
                date(year, month, day)
            except ValueError as err:
                raise EventValidationError(CONF_EVENT_DATE, "Invalid date") from err
            return f"{year}-{month:02d}-{day:02d}", False

    if year_unknown is not False:
        m = re.fullmatch(r"(\d{1,2})-(\d{1,2})", date_str)
        if m:
            month, day = int(m.group(1)), int(m.group(2))
            try:
                date(2000, month, day)
            except ValueError as err:
                raise EventValidationError(CONF_EVENT_DATE, "Invalid date") from err
            return f"{month:02d}-{day:02d}", True

    raise EventValidationError(CONF_EVENT_DATE, "Invalid date")


def build_event_data(data: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate service/options-flow input and return normalized event data."""
    existing = existing or {}

    name = str(data.get(CONF_EVENT_NAME, "")).strip()
    if not name:
        raise EventValidationError(CONF_EVENT_NAME, "Name is required")

    event_type = data.get(CONF_EVENT_TYPE)
    if event_type not in EVENT_TYPES:
        raise EventValidationError(CONF_EVENT_TYPE, "Invalid event type")

    year_unknown = data.get(CONF_EVENT_YEAR_UNKNOWN)
    normalized_date, normalized_year_unknown = normalize_event_date(
        str(data.get(CONF_EVENT_DATE, "")),
        year_unknown if year_unknown is not None else None,
    )

    return {
        "_id": existing.get("_id") or str(uuid.uuid4())[:8],
        CONF_EVENT_NAME: name,
        CONF_EVENT_DATE: normalized_date,
        CONF_EVENT_TYPE: event_type,
        CONF_EVENT_CUSTOM_LABEL: str(data.get(CONF_EVENT_CUSTOM_LABEL, "")).strip(),
        CONF_EVENT_ICON: str(data.get(CONF_EVENT_ICON, "")).strip(),
        CONF_EVENT_YEAR_UNKNOWN: normalized_year_unknown,
    }


def event_names_match(first: str, second: str) -> bool:
    """Return whether two event names should be treated as duplicates."""
    return first.strip().casefold() == second.strip().casefold()
