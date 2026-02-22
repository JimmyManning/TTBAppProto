"""Typed request normalization for expected label metadata."""

from dataclasses import dataclass
from typing import Any

from ttb_label_verifier.validators.definitions import EXPECTED_INPUT_FIELDS
from ttb_label_verifier.validators.parsing import (
    parse_age_years,
    parse_bool_flag,
    parse_percentage_value,
)


@dataclass(frozen=True)
class NormalizedExpected:
    """Normalized expected metadata for one label validation."""

    payload: dict[str, Any]

    @classmethod
    def from_mapping(cls, raw: dict[str, Any] | None) -> "NormalizedExpected":
        """Create a normalized expected payload from raw API input."""
        source = dict(raw or {})
        normalized: dict[str, Any] = {}

        for key in EXPECTED_INPUT_FIELDS:
            value = source.get(key, "")
            if key == "alcoholContent":
                normalized[key] = parse_percentage_value(value)
            else:
                normalized[key] = str(value).strip() if value is not None else ""

        age = parse_age_years(source.get("ageYears"))
        if age is not None:
            normalized["ageYears"] = age
        elif "ageYears" in source:
            normalized["ageYears"] = source.get("ageYears")

        for flag in ("fdcYellow5", "cochinealExtract", "carmine"):
            if flag in source:
                normalized[flag] = parse_bool_flag(source.get(flag))

        return cls(payload=normalized)

    def validate_required(self, requires_age: bool, prefix: str = "expected") -> str | None:
        """Return first validation error for required fields, otherwise None."""
        for key in EXPECTED_INPUT_FIELDS:
            value = self.payload.get(key)
            if key == "alcoholContent":
                if not isinstance(value, float):
                    return f"{prefix}.{key} must be a numeric percentage (0-100]"
                continue
            if not isinstance(value, str) or not value.strip():
                return f"{prefix}.{key} is required"

        if requires_age and parse_age_years(self.payload.get("ageYears")) is None:
            class_type_code = self.payload.get("classTypeCode", "")
            return f"{prefix}.ageYears is required for classTypeCode {class_type_code}"

        return None
