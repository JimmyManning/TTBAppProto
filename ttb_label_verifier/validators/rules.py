"""Field-level validation rules."""

import re
from typing import Any

from ttb_label_verifier.validators.parsing import (
    parse_age_years,
    parse_percentage_value,
)
from ttb_label_verifier.validators.policy import (
    CLASS_TYPE_CODE_PATTERN,
    load_class_type_code_labels,
)
from ttb_label_verifier.validators.text import (
    normalize_loose,
    normalize_strict_spaces,
    similarity,
)


def verify_warning(raw_text: str, expected_warning: str) -> tuple[str, bool, float]:
    """Validate government warning with exact text + uppercase header rules."""
    expected = normalize_strict_spaces(expected_warning)
    raw = normalize_strict_spaces(raw_text)
    contains_exact = expected in raw
    has_uppercase_header = "GOVERNMENT WARNING:" in raw
    passed = contains_exact and has_uppercase_header

    if passed:
        return expected, True, 1.0

    if not raw:
        return "No warning-like text found. Reason: OCR text is empty.", False, 0.0

    lines = [line.strip() for line in re.split(r"\n+", raw_text or "") if line.strip()]
    if not lines:
        lines = [raw]

    best_line = ""
    best_score = 0.0
    for line in lines:
        score = similarity(expected, line)
        if score > best_score:
            best_score = score
            best_line = normalize_strict_spaces(line)

    reasons: list[str] = []
    if not contains_exact:
        reasons.append("warning text is not an exact full-text match")
    if not has_uppercase_header:
        reasons.append("missing exact uppercase header 'GOVERNMENT WARNING:'")

    closest = best_line or "No close warning line found"
    detected = f"Closest: {closest} | Reason: {'; '.join(reasons)}"
    return detected, False, max(best_score, 0.0)


def verify_alcohol_content(raw_text: str, expected_value: Any) -> tuple[str, bool, float]:
    r"""Validate alcohol content as percentage + allowed alc/alcohol by/\/ vol/volume format."""
    expected_pct = parse_percentage_value(expected_value)
    if expected_pct is None:
        return "Invalid expected alcohol percentage", False, 0.0

    strict = normalize_strict_spaces(raw_text)

    if re.search(r"\babv\b", strict, re.IGNORECASE):
        return "ABV not allowed", False, 0.0

    pattern = re.compile(
        r"(?P<pct>\d{1,2}(?:\.\d+)?)\s*%\s*"
        r"(?P<phrase>(?:alc(?:ohol)?\.?|alcohol)\s*(?:/\s*by|by|/)\s*(?:vol(?:ume)?\.?|volume))",
        re.IGNORECASE,
    )
    matches = list(pattern.finditer(strict))
    if not matches:
        return "Missing required alcohol/volume phrasing", False, 0.0

    best_pct = None
    best_diff = float("inf")
    best_text = ""
    for match in matches:
        pct = float(match.group("pct"))
        diff = abs(pct - expected_pct)
        if diff < best_diff:
            best_diff = diff
            best_pct = pct
            best_text = f"{match.group('pct')}% {match.group('phrase')}"

    if best_pct is None:
        return "Missing required alcohol/volume phrasing", False, 0.0

    passed = best_diff <= 0.2
    score = max(0.0, 1.0 - min(best_diff / max(expected_pct, 1.0), 1.0))

    proof_word_present = bool(re.search(r"\bproof\b", strict, re.IGNORECASE))
    proof_matches = list(re.finditer(r"(?P<proof>\d{1,3}(?:\.\d+)?)\s*(?:°|deg(?:rees?)?)?\s*proof\b", strict, re.IGNORECASE))
    if proof_word_present:
        if not proof_matches:
            return "Proof text present without numeric value", False, 0.0

        expected_proof = expected_pct * 2.0
        best_proof = None
        best_proof_diff = float("inf")
        for match in proof_matches:
            proof_val = float(match.group("proof"))
            diff = abs(proof_val - expected_proof)
            if diff < best_proof_diff:
                best_proof_diff = diff
                best_proof = proof_val

        proof_passed = best_proof is not None and best_proof_diff <= 0.5
        proof_score = max(0.0, 1.0 - min(best_proof_diff / max(expected_proof, 1.0), 1.0))

        passed = passed and proof_passed
        score = (score + proof_score) / 2.0
        if best_proof is not None:
            best_text = f"{best_text} ({best_proof:g} Proof)"

    return best_text, passed, score


def verify_class_type_code(raw_text: str, class_type_code: str) -> tuple[str, bool, float]:
    """Validate class/type code format and scan OCR text for code or mapped label."""
    code = (class_type_code or "").strip()
    if not CLASS_TYPE_CODE_PATTERN.fullmatch(code):
        return "Invalid code format", False, 0.0

    strict = normalize_strict_spaces(raw_text)
    loose = normalize_loose(raw_text)
    code_pattern = re.compile(rf"(^|[^A-Za-z0-9]){re.escape(code)}($|[^A-Za-z0-9])")
    code_found = bool(code_pattern.search(strict))

    mapped_label = load_class_type_code_labels().get(code, "")
    label_found = False
    label_score = 0.0

    if mapped_label:
        mapped_label_loose = normalize_loose(mapped_label)
        if mapped_label_loose and mapped_label_loose in loose:
            label_found = True
            label_score = 1.0
        else:
            lines = [line.strip() for line in re.split(r"\n+", strict) if line.strip()]
            if not lines and strict:
                lines = [strict]
            if lines:
                label_score = max(similarity(mapped_label, line) for line in lines)
                label_found = label_score >= 0.82

    passed = code_found or label_found
    if label_found:
        detected = mapped_label
        score = label_score
    elif code_found:
        detected = code
        score = 1.0
    else:
        detected = mapped_label or code
        score = max(label_score, 0.0)

    return detected, passed, score


def verify_age_statement(raw_text: str, expected_age_years: Any) -> tuple[str, bool, float]:
    """Validate that expected age statement appears in OCR text."""
    expected_age = parse_age_years(expected_age_years)
    if expected_age is None:
        return "Invalid expected age", False, 0.0

    strict = normalize_strict_spaces(raw_text)
    patterns = [
        re.compile(r"(?P<age>\d{1,3}(?:\.\d+)?)\s*(?:years?|yrs?|year|yr)\s*old", re.IGNORECASE),
        re.compile(r"aged\s*(?P<age>\d{1,3}(?:\.\d+)?)\s*(?:years?|yrs?|year|yr)?", re.IGNORECASE),
        re.compile(r"stored\s*(?P<age>\d{1,3}(?:\.\d+)?)\s*(?:years?|yrs?|year|yr)", re.IGNORECASE),
    ]

    matches: list[tuple[float, str]] = []
    for pattern in patterns:
        for match in pattern.finditer(strict):
            age = float(match.group("age"))
            matches.append((age, normalize_strict_spaces(match.group(0))))

    if not matches:
        if expected_age < 4:
            return "Age required when less than 4 years - Age not detected.", False, 0.0
        return "Age not required if >= 4 years.", True, 1.0

    best_age = None
    best_text = ""
    best_diff = float("inf")
    for age, text in matches:
        diff = abs(age - expected_age)
        if diff < best_diff:
            best_diff = diff
            best_age = age
            best_text = text

    passed = best_age is not None and best_diff <= 0.2
    score = max(0.0, 1.0 - min(best_diff / max(expected_age, 1.0), 1.0))
    return best_text or f"{best_age:g} years", passed, score


def verify_contains_additive(raw_text: str, additive_name: str) -> tuple[str, bool, float]:
    """Validate presence of 'contains' followed by the specified additive text."""
    normalized = normalize_loose(raw_text or "")
    additive_norm = normalize_loose(additive_name)
    if not normalized:
        return "OCR text is empty", False, 0.0

    contains_pattern = re.compile(rf"\bcontains\b\s*:?.*?\b{re.escape(additive_norm)}\b", re.IGNORECASE)
    if contains_pattern.search(normalized):
        return f"contains {additive_name}", True, 1.0

    additive_present = re.search(rf"\b{re.escape(additive_norm)}\b", normalized, re.IGNORECASE) is not None
    if additive_present:
        return f"{additive_name} detected without preceding 'contains'", False, 0.4

    return f"Missing 'contains {additive_name}'", False, 0.0
