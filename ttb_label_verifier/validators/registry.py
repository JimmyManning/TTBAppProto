"""Field validator registry and dispatch helpers."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ttb_label_verifier.validators.policy import should_skip_origin_validation
from ttb_label_verifier.validators.text import (
    extract_by_regex,
    normalize_loose,
    normalize_strict_spaces,
    similarity,
    verify_field,
)

FieldValidatorFn = Callable[[str, Any], tuple[str, bool, float]]


@dataclass(frozen=True)
class FieldValidatorSpec:
    """Metadata and callable for a field validator."""

    key: str
    label: str
    validator: FieldValidatorFn


def _validate_generic_field(raw_text: str, expected_value: Any) -> tuple[str, bool, float]:
    strict = normalize_strict_spaces(raw_text)
    loose = normalize_loose(raw_text)

    regex_candidate = extract_by_regex(strict, "")
    if regex_candidate:
        passed, score = verify_field(expected_value, regex_candidate)
        return regex_candidate, passed, score

    if normalize_loose(str(expected_value or "")) in loose:
        return str(expected_value), True, 1.0

    lines = [line.strip() for line in strict.split("\n") if line.strip()]
    best = ""
    best_score = 0.0
    for line in lines:
        score = similarity(str(expected_value or ""), line)
        if score > best_score:
            best_score = score
            best = line

    return (best or "Not found"), (best_score >= 0.82), best_score


def _build_regex_first_validator(field_key: str) -> FieldValidatorFn:
    def _validator(raw_text: str, expected_value: Any) -> tuple[str, bool, float]:
        strict = normalize_strict_spaces(raw_text)
        loose = normalize_loose(raw_text)

        regex_candidate = extract_by_regex(strict, field_key)
        if regex_candidate:
            passed, score = verify_field(str(expected_value or ""), regex_candidate)
            return regex_candidate, passed, score

        if normalize_loose(str(expected_value or "")) in loose:
            return str(expected_value), True, 1.0

        lines = [line.strip() for line in strict.split("\n") if line.strip()]
        best = ""
        best_score = 0.0
        for line in lines:
            score = similarity(str(expected_value or ""), line)
            if score > best_score:
                best_score = score
                best = line

        return (best or "Not found"), (best_score >= 0.82), best_score

    return _validator


def _build_origin_validator(default_validator: FieldValidatorFn) -> FieldValidatorFn:
    def _validator(raw_text: str, expected_value: Any) -> tuple[str, bool, float]:
        if should_skip_origin_validation(expected_value):
            return str(expected_value), True, 1.0
        return default_validator(raw_text, expected_value)

    return _validator


def build_field_registry(
    field_labels: dict[str, str],
    warning_validator: FieldValidatorFn,
    class_code_validator: FieldValidatorFn,
    alcohol_validator: FieldValidatorFn,
) -> dict[str, FieldValidatorSpec]:
    """Build key -> validator mapping with metadata."""
    generic_validator = _build_regex_first_validator("")
    net_contents_validator = _build_regex_first_validator("netContents")
    origin_base_validator = _build_regex_first_validator("origin")
    origin_validator = _build_origin_validator(origin_base_validator)

    validators: dict[str, FieldValidatorSpec] = {
        "brandName": FieldValidatorSpec("brandName", field_labels["brandName"], generic_validator),
        "classTypeCode": FieldValidatorSpec("classTypeCode", field_labels["classTypeCode"], class_code_validator),
        "alcoholContent": FieldValidatorSpec("alcoholContent", field_labels["alcoholContent"], alcohol_validator),
        "netContents": FieldValidatorSpec("netContents", field_labels["netContents"], net_contents_validator),
        "bottler": FieldValidatorSpec("bottler", field_labels["bottler"], generic_validator),
        "bottlerAddress": FieldValidatorSpec("bottlerAddress", field_labels["bottlerAddress"], generic_validator),
        "origin": FieldValidatorSpec("origin", field_labels["origin"], origin_validator),
        "govWarning": FieldValidatorSpec("govWarning", field_labels["govWarning"], warning_validator),
    }
    return validators
