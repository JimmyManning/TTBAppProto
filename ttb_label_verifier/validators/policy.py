"""Policy-driven class code and origin helper logic."""

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from ttb_label_verifier.validators.text import normalize_loose

CLASS_TYPE_CODE_PATTERN = re.compile(r"^(?:0|00|000|[0-9]{2,3}[A-Za-z]?)$")
CLASS_TYPE_CODES_TSV_PATH = Path(__file__).resolve().parent.parent.parent / "static" / "class_type_codes.tsv"

US_ORIGIN_ALIASES = {
    "united states",
    "united states of america",
    "usa",
    "us",
    "u s a",
    "u s",
}

US_STATE_ABBREVIATIONS = {
    "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga", "hi", "id", "il", "in", "ia", "ks",
    "ky", "la", "me", "md", "ma", "mi", "mn", "ms", "mo", "mt", "ne", "nv", "nh", "nj", "nm", "ny",
    "nc", "nd", "oh", "ok", "or", "pa", "ri", "sc", "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv",
    "wi", "wy", "dc",
}

US_STATE_NAMES = {
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado", "connecticut", "delaware", "florida",
    "georgia", "hawaii", "idaho", "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana", "maine",
    "maryland", "massachusetts", "michigan", "minnesota", "mississippi", "missouri", "montana", "nebraska",
    "nevada", "new hampshire", "new jersey", "new mexico", "new york", "north carolina", "north dakota", "ohio",
    "oklahoma", "oregon", "pennsylvania", "rhode island", "south carolina", "south dakota", "tennessee", "texas",
    "utah", "vermont", "virginia", "washington", "west virginia", "wisconsin", "wyoming", "district of columbia",
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


def class_code_requires_age(class_type_code: str) -> bool:
    """Return True for class codes that require age statements per BAM Chapter 8 rules."""
    code = (class_type_code or "").strip()
    if not code:
        return False
    label = load_class_type_code_labels().get(code, "").upper()
    if not label:
        return False

    return "SPIRIT" in label or ("WHISKY" in label and "SOUR" not in label) or (
        "BRANDY" in label and "CORDIAL" not in label
    ) or "TEQUILA" in label or "SLIVOVITZ" in label or ("RUM" in label and "CORDIAL" not in label) or "ROCK" in label \
        or "MESCAL" in label or "KIRSCHWASSER" in label or "GRAPPA" in label or "ARMAGNAC" in label


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
