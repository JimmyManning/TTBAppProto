"""Generate API example payloads for OpenAPI and integration docs."""

from __future__ import annotations

import json
from pathlib import Path

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "docs" / "examples"


def _write_json(path: Path, payload: dict) -> None:
    """Write a JSON payload with stable formatting."""
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    """Generate request and response example files."""
    EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)

    validate_request = {
        "expected": {
            "brandName": "OLD TOM DISTILLERY",
            "classTypeCode": "101",
            "alcoholContent": 45,
            "netContents": "750 mL",
            "bottler": "Bottled by Old Tom Distillery, Frankfort, KY",
            "bottlerAddress": "123 Main St, Frankfort, KY",
            "origin": "United States",
            "ageYears": 4,
            "fdcYellow5": False,
            "cochinealExtract": False,
            "carmine": False,
        }
    }

    validate_response = {
        "filename": "label-1.png",
        "autoPass": True,
        "needsReview": False,
        "comparisons": [
            {
                "key": "brandName",
                "label": "Brand Name",
                "expected": "OLD TOM DISTILLERY",
                "detected": "OLD TOM DISTILLERY",
                "pass": True,
                "score": 1.0,
            }
        ],
        "extractedText": "OLD TOM DISTILLERY\n45% Alc./Vol.\n750 mL",
    }

    batch_response = {
        "total": 2,
        "autoPass": 1,
        "needsReview": 1,
        "results": [
            {
                "filename": "label1.png",
                "autoPass": True,
                "needsReview": False,
                "comparisons": [],
                "extractedText": "...",
            },
            {
                "filename": "label2.png",
                "autoPass": False,
                "needsReview": True,
                "comparisons": [],
                "extractedText": "...",
            },
        ],
    }

    _write_json(EXAMPLES_DIR / "validate-request.json", validate_request)
    _write_json(EXAMPLES_DIR / "validate-response.json", validate_response)
    _write_json(EXAMPLES_DIR / "batch-response.json", batch_response)


if __name__ == "__main__":
    main()
