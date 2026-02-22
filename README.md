# AI-Powered Alcohol Label Verification Prototype

![CI](https://github.com/YOUR_GITHUB_USERNAME/TBBAppProto/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.13-blue.svg)

> Replace `YOUR_GITHUB_USERNAME/TBBAppProto` with your actual GitHub repo path after publishing.

Standalone proof-of-concept for TTB-style label review with OCR-assisted verification and batch processing.

## What this prototype does

- Upload one or many label images at once (batch mode).
- Extract text from each label using backend OCR (Tesseract via API).
- Compare extracted content against application metadata fields:
  - Brand name
  - Class/type code
  - Alcohol content (%)
  - Net contents
  - Bottler/producer
  - Country of origin
  - Government warning statement
  - Age statement (years), when required for class/type
- Apply practical matching rules:
  - Fuzzy matching for routine fields (handles case/punctuation differences like `STONE'S THROW` vs `Stone's Throw`)
  - Strict check for government warning statement (exact statement + uppercase `GOVERNMENT WARNING:`)
  - Alcohol format enforcement: `% + alc/alcohol + by|/ + vol/volume`; `ABV` is rejected
  - Proof consistency check when proof appears (`proof = 2 × ABV`)
  - Origin validation auto-skipped for USA/United States/U.S. states
- Show per-label PASS/REVIEW output and batch summary.

## Why this architecture

- **Standalone**: no COLA integration required.
- **Firewall-friendly**: OCR runs locally on the same backend using on-host Tesseract (no external ML API calls).
- **Simple UX**: single-page workflow designed for mixed technical comfort levels.
- **Fast iteration**: Flask serves static assets and can be deployed quickly.

## Tech stack

- Python 3.11+ (tested with Python 3.13)
- Flask (light web host)
- Backend OCR: pytesseract + local Tesseract binary
- Vanilla JavaScript + CSS

## Repository layout

- `ttb_label_verifier/` — Python application package (factory, routes, OCR, validation)
- `templates/` — HTML templates
- `static/` — frontend JS/CSS assets
- `tests/` — unit tests
- `docs/` — architecture and design docs
- `.github/workflows/` — CI + Azure deployment workflows

## Python standards alignment

The repository now follows a package-based Python web app structure and includes tooling configuration in `pyproject.toml` aligned to Google-style Python practices:

- module/function docstrings
- clear separation of concerns (routing vs domain logic vs OCR)
- typed helper functions
- lint/format settings (`ruff`, `black`, `isort`) with Google-style docstring convention
- CI lint gate via GitHub Actions (`.github/workflows/ci.yml`)

## Run locally

1. Create and activate a virtual environment
2. Install dependencies
3. Run Flask app

Example:

- `python3 -m venv .venv`
- `source .venv/bin/activate`
- `pip install -r requirements.txt`
- `python app.py`

Open: `http://127.0.0.1:5001`

UI notes:

- The web form includes an optional guided `classTypeCode` picker grouped by ID ranges (first digit grouping), then specific code/type selection.
- Net contents input uses amount + common unit dropdown.
- Age statement field is included and is required when class/type rules require it.

## Run unit tests

- `python -m unittest discover -s tests -p "test_*.py" -v`

## Run lint checks

- `pip install -r requirements-dev.txt`
- `ruff check .`

## Makefile shortcuts

- `make run` — start the Flask app
- `make test` — run unit tests
- `make lint` — run lint checks
- `make format` — run `isort` and `black`
- `make check` — run lint + tests

## Deployment

This app can be deployed on any Python web host (Azure App Service, Render, Railway, etc.) using:

- Start command: `python app.py`
- Python version: 3.11+

Azure deployment workflow is available at [.github/workflows/deploy-azure.yml](.github/workflows/deploy-azure.yml).

Required GitHub secrets:

- `AZURE_WEBAPP_NAME`
- `AZURE_WEBAPP_PUBLISH_PROFILE`

## Automated validation API

The prototype APIs are image-upload only. OCR is always performed on the backend.

Endpoints:

- `POST /api/validate` (single label)
- `POST /api/validate/batch` (many labels)

Base URL (local): `http://127.0.0.1:5001`

Content type:

- `multipart/form-data` (required)

### Single label

Multipart body (`form-data`):

- `image` (file)
- `expected` (JSON string object) with all required keys:
  - `brandName`
  - `classTypeCode`
  - `alcoholContent` (number, percent in range `(0, 100]`)
  - `netContents`
  - `bottler`
  - `origin`
  - `ageYears` (required only for class/type codes where age is required by current rules)
- `govWarning` is not accepted from API callers; it is enforced as a backend constant.

Backend-enforced warning text (required case):

`GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink alcoholic beverages during pregnancy because of the risk of birth defects.`

`(2) Consumption of alcoholic beverages impairs your ability to drive a car or operate machinery, and may cause health problems.`
- `filename` (optional string)

### Batch labels

Multipart body (`form-data`):

- `images` (multiple files under same key)
- `expected` (JSON string object) for shared expected values (all keys above required)
- `expectedList` (optional JSON array of objects) for per-image expected values; must match number of files and each object must include all keys above

Response includes per-field comparisons and an `autoPass` / `needsReview` decision.

### Quick API examples

Single label (image upload):

- `curl -X POST http://127.0.0.1:5001/api/validate -F "image=@/absolute/path/label.png" -F 'expected={"brandName":"OLD TOM DISTILLERY","classTypeCode":"101","alcoholContent":"45% Alc./Vol. (90 Proof)","netContents":"750 mL","bottler":"Bottled by Old Tom Distillery, Frankfort, KY","origin":"Product of USA"}'`
- `curl -X POST http://127.0.0.1:5001/api/validate -F "image=@/absolute/path/label.png" -F 'expected={"brandName":"OLD TOM DISTILLERY","classTypeCode":"101","alcoholContent":45,"netContents":"750 mL","bottler":"Bottled by Old Tom Distillery, Frankfort, KY","origin":"Product of USA","ageYears":4}'`

Batch (image upload):

- `curl -X POST http://127.0.0.1:5001/api/validate/batch -F "images=@/absolute/path/label1.png" -F "images=@/absolute/path/label2.png" -F 'expected={"brandName":"OLD TOM DISTILLERY","classTypeCode":"101","alcoholContent":"45% Alc./Vol. (90 Proof)","netContents":"750 mL","bottler":"Bottled by Old Tom Distillery, Frankfort, KY","origin":"Product of USA"}'`
- `curl -X POST http://127.0.0.1:5001/api/validate/batch -F "images=@/absolute/path/label1.png" -F "images=@/absolute/path/label2.png" -F 'expected={"brandName":"OLD TOM DISTILLERY","classTypeCode":"101","alcoholContent":45,"netContents":"750 mL","bottler":"Bottled by Old Tom Distillery, Frankfort, KY","origin":"Product of USA","ageYears":4}'`

### Response shape

Single endpoint returns:

- `filename`
- `autoPass` (boolean)
- `needsReview` (boolean)
- `comparisons[]` with `key`, `label`, `expected`, `detected`, `pass`, `score`

Batch endpoint returns:

- `total`
- `autoPass`
- `needsReview`
- `results[]` (each item matches single response shape)

Common error responses:

- `400` for malformed payloads (wrong content type, bad JSON, missing files, missing required fields)
- `503` when OCR runtime is unavailable

When government warning fails strict match, the response now includes the closest detected warning-like text and explicit mismatch reasons.

### OCR dependency for image upload mode

Image upload mode requires both:

- Python packages in `requirements.txt` (`pillow`, `pytesseract`)
- System Tesseract binary installed and available on PATH

If Tesseract is not installed, image API calls return a clear `503` message.

## Assumptions and trade-offs

- OCR quality drives accuracy; glare/angle-heavy photos may still require manual review.
- Bold-style detection for warning text is not implemented in this prototype (text content and uppercase header are enforced).
- Field extraction for ABV/net contents uses regex heuristics for speed.
- Processing speed depends on image size and server resources; batch handling is currently sequential for predictable performance.

## Future improvements

- Add image preprocessing (deskew, contrast boost, glare mitigation).
- Add confidence-weighted queue triage for agents.
- Add configurable beverage-specific rule profiles (beer/wine/spirits).
- Add export of review output (CSV/PDF audit report).
- Add optional server-side OCR model for controlled offline environments.

## Synthetic test dataset

A generated dataset for stress/functional testing is included:

- [tests/synthetic_dataset/README.md](tests/synthetic_dataset/README.md)
- 100 images under [tests/synthetic_dataset/images](tests/synthetic_dataset/images)
- expected metadata + designed pass/fail outcomes in JSON/CSV manifests
