"""Flask routes and request parsing for web and API endpoints."""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify, render_template, request

from ttb_label_verifier.frontend_data import (
    load_countries,
    load_frontend_config,
)
from ttb_label_verifier.ocr import ocr_image_file
from ttb_label_verifier.request_models import NormalizedExpected
from ttb_label_verifier.validation import (
    EXPECTED_INPUT_FIELDS,
    FIELD_LABELS,
    OPTIONAL_FIELD_LABELS,
    class_code_requires_age,
    validate_label,
)

api_blueprint = Blueprint("api", __name__)
REQUIRED_FIELDS = tuple(EXPECTED_INPUT_FIELDS)
UNSUPPORTED_CONTENT_TYPE_MESSAGE = "Only multipart/form-data with image upload is supported"
MAX_BATCH_IMAGES = 50
OPENAPI_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "docs" / "openapi.yaml"


def _get_max_batch_images() -> int:
    """Get max upload count from frontend config with safe fallback."""
    frontend_config = load_frontend_config()
    value = frontend_config.get("maxBatchImages")
    if isinstance(value, int) and value > 0:
        return value
    return MAX_BATCH_IMAGES


def _get_expected_from_form(form_data: Mapping[str, Any], fallback: dict[str, Any] | None = None) -> tuple[dict[str, Any], str | None]:
    """Extract expected fields from form-data payload."""
    expected_json = form_data.get("expected")
    if expected_json:
        try:
            parsed = json.loads(expected_json)
            if not isinstance(parsed, dict):
                return {}, "expected must be a JSON object"
            return parsed, None
        except json.JSONDecodeError:
            return {}, "expected must be valid JSON"

    expected = dict(fallback or {})
    for key in EXPECTED_INPUT_FIELDS:
        if key in form_data:
            expected[key] = form_data.get(key, "")
    return expected, None


def _ocr_error_status(message: str) -> int:
    """Map OCR error message text to HTTP status code."""
    if "Tesseract" in message or "dependencies" in message:
        return 503
    return 400


def _validate_required_expected_fields(expected: dict[str, Any], prefix: str = "expected") -> str | None:
    """Validate that all required expected fields are present and non-empty."""
    if not isinstance(expected, dict):
        return f"{prefix} must be an object"

    normalized = NormalizedExpected.from_mapping(expected)
    class_type_code = str(normalized.payload.get("classTypeCode", "") or "").strip()
    requires_age = class_code_requires_age(class_type_code)
    return normalized.validate_required(requires_age=requires_age, prefix=prefix)


def _build_batch_response(results: list[dict[str, Any]]) -> tuple[dict[str, Any], int]:
    """Build a normalized batch validation response body."""
    auto_pass = sum(1 for item in results if item["autoPass"])
    return (
        {
            "total": len(results),
            "autoPass": auto_pass,
            "needsReview": len(results) - auto_pass,
            "results": results,
        },
        200,
    )


@api_blueprint.get("/")
def index():
    """Render the main web UI."""
    return render_template("index.html")


@api_blueprint.get("/health")
def health():
    """Return service health status."""
    return {"status": "ok"}


@api_blueprint.get("/api/config")
def api_config():
    """Return backend-owned field definitions for UI alignment."""
    frontend_config = load_frontend_config()
    max_batch_images = _get_max_batch_images()

    return {
        "requiredFields": list(REQUIRED_FIELDS),
        "fieldLabels": FIELD_LABELS,
        "optionalFieldLabels": OPTIONAL_FIELD_LABELS,
        "maxBatchImages": max_batch_images,
        "defaultOrigin": frontend_config.get("defaultOrigin", "United States"),
        "countries": load_countries(),
        "additiveFlags": frontend_config.get("additiveFlags", []),
        "numericSanitization": frontend_config.get("numericSanitization", {}),
    }


@api_blueprint.get("/api/openapi.yaml")
def api_openapi_schema():
    """Return the published OpenAPI schema document."""
    if not OPENAPI_SCHEMA_PATH.exists():
        return jsonify({"error": "OpenAPI schema not found"}), 404
    return OPENAPI_SCHEMA_PATH.read_text(encoding="utf-8"), 200, {"Content-Type": "application/yaml; charset=utf-8"}


@api_blueprint.post("/api/validate")
def api_validate_single():
    """Validate one label from multipart image upload."""
    content_type = request.content_type or ""

    if not content_type.startswith("multipart/form-data"):
        return jsonify({"error": UNSUPPORTED_CONTENT_TYPE_MESSAGE}), 400

    file = request.files.get("image")
    expected, error = _get_expected_from_form(request.form)
    filename = request.form.get("filename") or (file.filename if file else None)

    if error:
        return jsonify({"error": error}), 400

    missing_error = _validate_required_expected_fields(expected)
    if missing_error:
        return jsonify({"error": missing_error}), 400

    extracted_text, ocr_error = ocr_image_file(file)
    if ocr_error:
        return jsonify({"error": ocr_error}), _ocr_error_status(ocr_error)

    result = validate_label(extracted_text, expected, filename)
    result["extractedText"] = extracted_text
    return jsonify(result)


@api_blueprint.post("/api/validate/batch")
def api_validate_batch():
    """Validate a batch of labels from multipart image upload."""
    content_type = request.content_type or ""

    if not content_type.startswith("multipart/form-data"):
        return jsonify({"error": UNSUPPORTED_CONTENT_TYPE_MESSAGE}), 400

    files = request.files.getlist("images")
    expected, error = _get_expected_from_form(request.form)
    expected_list_json = request.form.get("expectedList")
    expected_list = None

    if expected_list_json:
        try:
            expected_list = json.loads(expected_list_json)
            if not isinstance(expected_list, list):
                return jsonify({"error": "expectedList must be a JSON array"}), 400
        except json.JSONDecodeError:
            return jsonify({"error": "expectedList must be valid JSON"}), 400

    if error:
        return jsonify({"error": error}), 400
    if not files:
        return jsonify({"error": "No images uploaded. Use form-data key 'images'."}), 400
    max_batch_images = _get_max_batch_images()
    if len(files) > max_batch_images:
        return jsonify({"error": f"Maximum {max_batch_images} images are allowed per request"}), 400
    if expected_list is not None and len(expected_list) != len(files):
        return jsonify({"error": "expectedList length must match number of images"}), 400

    if expected_list is None:
        missing_error = _validate_required_expected_fields(expected)
        if missing_error:
            return jsonify({"error": missing_error}), 400

    results: list[dict[str, Any]] = []
    for index, file in enumerate(files):
        item_expected = expected_list[index] if expected_list is not None else expected
        if not isinstance(item_expected, dict):
            return jsonify({"error": f"expectedList[{index}] must be an object"}), 400

        item_missing_error = _validate_required_expected_fields(item_expected, prefix=f"expectedList[{index}]")
        if item_missing_error:
            return jsonify({"error": item_missing_error}), 400

        extracted_text, ocr_error = ocr_image_file(file)
        if ocr_error:
            return jsonify({"error": f"images[{index}]: {ocr_error}"}), _ocr_error_status(ocr_error)

        validation = validate_label(extracted_text, item_expected, file.filename or f"label-{index + 1}")
        validation["extractedText"] = extracted_text
        results.append(validation)

    response_body, status = _build_batch_response(results)
    return jsonify(response_body), status
