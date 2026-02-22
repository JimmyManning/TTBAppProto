"""Input parsing helpers used by request and validation layers."""

import re
from typing import Any


def parse_percentage_value(value: Any) -> float | None:
    """Parse expected alcohol percentage from number or numeric text."""
    if isinstance(value, int | float) and not isinstance(value, bool):
        parsed = float(value)
    elif isinstance(value, str):
        raw = value.strip().rstrip("%")
        if not raw:
            return None
        try:
            parsed = float(raw)
        except ValueError:
            return None
    else:
        return None

    if parsed <= 0 or parsed > 100:
        return None
    return parsed


def parse_age_years(value: Any) -> float | None:
    """Parse age in years from numeric or numeric-like value."""
    if value is None:
        return None
    if isinstance(value, int | float) and not isinstance(value, bool):
        parsed = float(value)
    elif isinstance(value, str):
        raw = value.strip().lower()
        raw = re.sub(r"\s*(years?|yrs?|year|yr)\.?\s*", "", raw)
        if not raw:
            return None
        try:
            parsed = float(raw)
        except ValueError:
            return None
    else:
        return None

    if parsed <= 0 or parsed > 150:
        return None
    return parsed


def parse_bool_flag(value: Any) -> bool:
    """Parse optional flag values from booleans/strings/numbers."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False
