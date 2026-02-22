"""Shared text normalization and matching utilities."""

import re


def normalize_loose(value: str) -> str:
    """Normalize text for case-insensitive fuzzy comparisons."""
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


def verify_field(expected: str, detected: str, mode: str = "fuzzy") -> tuple[bool, float]:
    """Compare expected and detected values for pass/fail and score."""
    if not expected:
        return True, 1.0

    if mode == "exact":
        is_match = expected == detected
        return is_match, 1.0 if is_match else 0.0

    score = similarity(expected, detected)
    return score >= 0.82, score


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
