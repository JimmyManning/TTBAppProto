"""Validation and matching logic for alcohol label checks."""

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

FIELD_LABELS = {
    "brandName": "Brand Name",
    "classTypeCode": "Class/Type Code",
    "alcoholContent": "Alcohol Content (%)",
    "netContents": "Net Contents",
    "bottler": "Bottler/Producer",
    "origin": "Country of Origin",
    "govWarning": "Government Warning",
}

OPTIONAL_FIELD_LABELS = {
    "ageYears": "Age Statement (Years)",
}

CLASS_TYPE_CODE_PATTERN = re.compile(r"^(?:0|00|000|[0-9]{2,3}[A-Za-z]?)$")
CLASS_TYPE_CODES_TSV_PATH = Path(__file__).resolve().parent.parent / "static" / "class_type_codes.tsv"

REQUIRED_GOV_WARNING = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
    "drink alcoholic beverages during pregnancy because of the risk of birth defects.\n\n"
    "(2) Consumption of alcoholic beverages impairs your ability to drive a car or "
    "operate machinery, and may cause health problems."
)

EXPECTED_INPUT_FIELDS = (
    "brandName",
    "classTypeCode",
    "alcoholContent",
    "netContents",
    "bottler",
    "origin",
)

US_ORIGIN_ALIASES = {
    "united states",
    "united states of america",
    "usa",
    "us",
    "u s a",
    "u s",
}

US_STATE_ABBREVIATIONS = {
    "al",
    "ak",
    "az",
    "ar",
    "ca",
    "co",
    "ct",
    "de",
    "fl",
    "ga",
    "hi",
    "id",
    "il",
    "in",
    "ia",
    "ks",
    "ky",
    "la",
    "me",
    "md",
    "ma",
    "mi",
    "mn",
    "ms",
    "mo",
    "mt",
    "ne",
    "nv",
    "nh",
    "nj",
    "nm",
    "ny",
    "nc",
    "nd",
    "oh",
    "ok",
    "or",
    "pa",
    "ri",
    "sc",
    "sd",
    "tn",
    "tx",
    "ut",
    "vt",
    "va",
    "wa",
    "wv",
    "wi",
    "wy",
    "dc",
}

US_STATE_NAMES = {
    "alabama",
    "alaska",
    "arizona",
    "arkansas",
    "california",
    "colorado",
    "connecticut",
    "delaware",
    "florida",
    "georgia",
    "hawaii",
    "idaho",
    "illinois",
    "indiana",
    "iowa",
    "kansas",
    "kentucky",
    "louisiana",
    "maine",
    "maryland",
    "massachusetts",
    "michigan",
    "minnesota",
    "mississippi",
    "missouri",
    "montana",
    "nebraska",
    "nevada",
    "new hampshire",
    "new jersey",
    "new mexico",
    "new york",
    "north carolina",
    "north dakota",
    "ohio",
    "oklahoma",
    "oregon",
    "pennsylvania",
    "rhode island",
    "south carolina",
    "south dakota",
    "tennessee",
    "texas",
    "utah",
    "vermont",
    "virginia",
    "washington",
    "west virginia",
    "wisconsin",
    "wyoming",
    "district of columbia",
}


@lru_cache(maxsize=1)
def load_class_type_code_labels() -> dict[str, str]:
    """Load class/type code -> label mappings from the TSV source."""
    if not CLASS_TYPE_CODES_TSV_PATH.exists():
        return {}

    labels: dict[str, str] = {}
    with CLASS_TYPE_CODES_TSV_PATH.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            parts = line.split("\t", maxsplit=1)
            if len(parts) != 2:
                continue
            code = parts[0].strip()
            label = parts[1].strip()
            if code and label and code not in labels:
                labels[code] = label
    return labels


def normalize_loose(value: str) -> str:
    """Normalize text for case-insensitive fuzzy comparisons.

    Args:
        value: Input text.

    Returns:
        A lowercased, punctuation-reduced, whitespace-normalized string.
    """
    value = (value or "").lower()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_strict_spaces(value: str) -> str:
    """Normalize whitespace while preserving letter casing and punctuation."""
    return re.sub(r"\s+", " ", value or "").strip()


def levenshtein(a: str, b: str) -> int:
    """Compute Levenshtein distance between two strings."""
    m = len(a)
    n = len(b)
    if m == 0:
        return n
    if n == 0:
        return m

    dp = [[0 for _ in range(n + 1)] for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,
                dp[i][j - 1] + 1,
                dp[i - 1][j - 1] + cost,
            )

    return dp[m][n]


def similarity(a: str, b: str) -> float:
    """Return a normalized similarity score in the range [0.0, 1.0]."""
    x = normalize_loose(a)
    y = normalize_loose(b)
    if not x and not y:
        return 1.0
    if not x or not y:
        return 0.0
    max_len = max(len(x), len(y))
    return 1.0 - (levenshtein(x, y) / max_len)


def extract_by_regex(text: str, key: str) -> str:
    """Extract canonical field text using field-specific regular expressions."""
    patterns = {
        "netContents": re.compile(r"(\d{2,4}\s*(?:ml|mL|l|L|fl\.?\s*oz\.?))", re.IGNORECASE),
        "origin": re.compile(r"(product\s+of\s+[a-z\s]+)", re.IGNORECASE),
    }

    pattern = patterns.get(key)
    if not pattern:
        return ""
    match = pattern.search(text or "")
    return match.group(1) if match else ""


def verify_field(expected: str, detected: str, mode: str = "fuzzy") -> tuple[bool, float]:
    """Compare expected and detected values for pass/fail and score."""
    if not expected:
        return True, 1.0

    if mode == "exact":
        is_match = expected == detected
        return is_match, 1.0 if is_match else 0.0

    score = similarity(expected, detected)
    return score >= 0.82, score


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

    # If proof is present, enforce proof == 2 * ABV (US proof scale).
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


def class_code_requires_age(class_type_code: str) -> bool:
    """Return True for class codes that require age statements per BAM Chapter 8 rules.

    Implemented for whisky classes containing neutral spirits (e.g., blended and
    spirit whisky family) identified by class/type label text.
    """
    code = (class_type_code or "").strip()
    if not code:
        return False
    label = load_class_type_code_labels().get(code, "").upper()
    if not label:
        return False

    return "SPIRIT" in label or ("WHISKY" in label and "SOUR" not in label) or \
        ("BRANDY" in label and "CORDIAL" not in label) or "TEQUILA" in label or "SLIVOVITZ" in label or \
        ("RUM" in label and "CORDIAL" not in label) or "ROCK" in label \
        or "MESCAL" in label or "KIRSCHWASSER" in label or "GRAPPA" in label \
        or "ARMAGNAC" in label
    
    


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
        else:
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


def should_skip_origin_validation(expected_value: Any) -> bool:
    """Return True when expected origin is U.S./USA or a U.S. state."""
    value = normalize_loose(str(expected_value or ""))
    value = re.sub(r"^product of\s+", "", value).strip()
    if not value:
        return False

    if value in US_ORIGIN_ALIASES or value in US_STATE_NAMES or value in US_STATE_ABBREVIATIONS:
        return True

    tokens = set(value.split())
    if value in US_STATE_NAMES:
        return True
    if len(tokens) == 1 and next(iter(tokens)) in US_STATE_ABBREVIATIONS:
        return True
    return False


def detect_field(raw_text: str, expected_value: Any, field_key: str) -> tuple[str, bool, float]:
    """Detect a field value from raw OCR text and evaluate against expectations."""
    if field_key != "govWarning" and not expected_value:
        return "", True, 1.0

    strict = normalize_strict_spaces(raw_text)
    loose = normalize_loose(raw_text)

    if field_key == "govWarning":
        return verify_warning(strict, expected_value)

    if field_key == "classTypeCode":
        return verify_class_type_code(strict, expected_value)

    if field_key == "alcoholContent":
        return verify_alcohol_content(strict, expected_value)

    if field_key == "origin" and should_skip_origin_validation(expected_value):
        return str(expected_value), True, 1.0

    regex_candidate = extract_by_regex(strict, field_key)
    if regex_candidate:
        passed, score = verify_field(expected_value, regex_candidate)
        return regex_candidate, passed, score

    if normalize_loose(expected_value) in loose:
        return expected_value, True, 1.0

    lines = [line.strip() for line in re.split(r"\n+", strict) if line.strip()]
    best = ""
    best_score = 0.0

    for line in lines:
        score = similarity(expected_value, line)
        if score > best_score:
            best_score = score
            best = line

    return (best or "Not found"), (best_score >= 0.82), best_score


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

    auto_pass = all(item["pass"] for item in comparisons)
    return {
        "filename": filename,
        "autoPass": auto_pass,
        "needsReview": not auto_pass,
        "comparisons": comparisons,
    }
