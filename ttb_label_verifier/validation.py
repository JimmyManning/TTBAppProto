"""Validation orchestration for alcohol label checks."""

from typing import Any

from ttb_label_verifier.validators.definitions import (
    EXPECTED_INPUT_FIELDS,
    FIELD_LABELS,
    OPTIONAL_ADDITIVE_FLAGS,
    OPTIONAL_FIELD_LABELS,
    REQUIRED_GOV_WARNING,
)
from ttb_label_verifier.validators.parsing import (
    parse_age_years,
    parse_bool_flag,
    parse_percentage_value,
)
from ttb_label_verifier.validators.policy import (
    class_code_requires_age,
    should_skip_origin_validation,
)
from ttb_label_verifier.validators.registry import build_field_registry
from ttb_label_verifier.validators.rules import (
    verify_age_statement,
    verify_alcohol_content,
    verify_class_type_code,
    verify_contains_additive,
    verify_warning,
)
from ttb_label_verifier.validators.text import normalize_loose

FIELD_VALIDATOR_REGISTRY = build_field_registry(
    field_labels=FIELD_LABELS,
    warning_validator=verify_warning,
    class_code_validator=verify_class_type_code,
    alcohol_validator=verify_alcohol_content,
)

__all__ = [
    "EXPECTED_INPUT_FIELDS",
    "FIELD_LABELS",
    "OPTIONAL_ADDITIVE_FLAGS",
    "OPTIONAL_FIELD_LABELS",
    "REQUIRED_GOV_WARNING",
    "class_code_requires_age",
    "detect_field",
    "normalize_loose",
    "parse_age_years",
    "parse_bool_flag",
    "parse_percentage_value",
    "should_skip_origin_validation",
    "validate_label",
    "verify_age_statement",
    "verify_alcohol_content",
    "verify_class_type_code",
    "verify_contains_additive",
    "verify_warning",
]


def detect_field(raw_text: str, expected_value: Any, field_key: str) -> tuple[str, bool, float]:
    """Detect a field value from raw OCR text and evaluate against expectations."""
    if field_key != "govWarning" and not expected_value:
        return "", True, 1.0

    validator = FIELD_VALIDATOR_REGISTRY.get(field_key)
    if not validator:
        return "Not found", False, 0.0

    return validator.validator(raw_text or "", expected_value)


def validate_label(extracted_text: str, expected: dict[str, Any], filename: str | None = None) -> dict[str, Any]:
    """Validate one label's extracted text against expected metadata fields."""
    comparisons: list[dict[str, Any]] = []
    for key, label in FIELD_LABELS.items():
        if key == "govWarning":
            expected_value = REQUIRED_GOV_WARNING
        else:
            expected_value = (expected or {}).get(key, "")
        detected, passed, score = detect_field(extracted_text or "", expected_value, key)
        comparisons.append(
            {
                "key": key,
                "label": label,
                "expected": expected_value,
                "detected": detected,
                "pass": passed,
                "score": round(score, 4),
            }
        )

    class_code = str((expected or {}).get("classTypeCode", "") or "")
    expected_age = (expected or {}).get("ageYears")
    age_required = class_code_requires_age(class_code)
    if age_required or expected_age is not None:
        if expected_age is None:
            detected = "Age required for this class/type code but not provided"
            passed = False
            score = 0.0
            expected_display: Any = "required"
        else:
            detected, passed, score = verify_age_statement(extracted_text or "", expected_age)
            expected_display = expected_age

        comparisons.append(
            {
                "key": "ageYears",
                "label": OPTIONAL_FIELD_LABELS["ageYears"],
                "expected": expected_display,
                "detected": detected,
                "pass": passed,
                "score": round(score, 4),
            }
        )

    for flag_key, additive_name in OPTIONAL_ADDITIVE_FLAGS.items():
        if parse_bool_flag((expected or {}).get(flag_key)):
            detected, passed, score = verify_contains_additive(extracted_text or "", additive_name)
            comparisons.append(
                {
                    "key": flag_key,
                    "label": OPTIONAL_FIELD_LABELS[flag_key],
                    "expected": True,
                    "detected": detected,
                    "pass": passed,
                    "score": round(score, 4),
                }
            )

    auto_pass = all(item["pass"] for item in comparisons)
    return {
        "filename": filename,
        "autoPass": auto_pass,
        "needsReview": not auto_pass,
        "comparisons": comparisons,
    }
