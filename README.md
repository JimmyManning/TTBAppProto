# Alcohol Label Verification Prototype

[![CI](https://github.com/JimmyManning/TBBAppProto/actions/workflows/ci.yml/badge.svg)](https://github.com/JimmyManning/TBBAppProto/actions/workflows/ci.yml)
[![Azure Deploy](https://github.com/JimmyManning/TBBAppProto/actions/workflows/main_ttblabelverifyer.yml/badge.svg)](https://github.com/JimmyManning/TBBAppProto/actions/workflows/main_ttblabelverifyer.yml)

Standalone Flask prototype for OCR-assisted alcohol label verification.

## What it does

- Accepts one or many label images.
- Extracts OCR text using local Tesseract.
- Compares OCR text against expected metadata.
- Returns field-level PASS/REVIEW results and batch summary.

Validated fields:

- `brandName`
- `classTypeCode`
- `alcoholContent`
- `netContents`
- `bottler`
- `bottlerAddress`
- `origin`
- backend-enforced `govWarning`
- optional `ageYears` when required by class/type policy
- optional additive checks (`fdcYellow5`, `cochinealExtract`, `carmine`)

## Tech stack

- Python 3.11+
- Flask
- Pillow + pytesseract + system Tesseract
- Vanilla JS/CSS (modular frontend under `static/js`)

## Project layout

- `ttb_label_verifier/` backend package
  - `routes.py` API + page routes
  - `ocr.py` OCR preprocessing/extraction
  - `validation.py` validation orchestration
  - `validators/` modular validator rules and helpers
  - `request_models.py` expected-payload normalization
  - `frontend_data.py` loaders for frontend config data
- `templates/` server-rendered HTML
- `static/js/` frontend modules (`main`, `form`, `api-client`, `guided-selection`, `render`)
- `static/data/` frontend config (`countries.json`, `frontend_config.json`)
- `docs/` architecture and API schema
- `tests/` backend tests

## Local run

1. `python3 -m venv .venv`
2. `source .venv/bin/activate`
3. `pip install -r requirements.txt`
4. `python app.py`

App runs at `http://127.0.0.1:5001`.

## Validation and test commands

- `make check` (lint + Python tests)
- `make lint`
- `make test`

Optional frontend behavior tests (Node 18+):

- `node --test tests/frontend/form.behavior.test.mjs`

Covered frontend behaviors:

- numeric sanitization
- 50-image limit messaging
- origin dropdown default
- additive checkbox mapping

## API summary

Endpoints:

- `GET /health`
- `GET /api/config`
- `GET /api/openapi.yaml`
- `POST /api/validate`
- `POST /api/validate/batch`

`/api/validate` and `/api/validate/batch` require `multipart/form-data` image upload.

Expected payload rules:

- `expected` is a JSON object string in form-data.
- Required keys: `brandName`, `classTypeCode`, `alcoholContent`, `netContents`, `bottler`, `bottlerAddress`, `origin`.
- `ageYears` is conditionally required for age-required class/type codes.
- `govWarning` is not caller-provided; it is validated against a backend constant.
- Optional additive flags: `fdcYellow5`, `cochinealExtract`, `carmine`.

Batch limits:

- Max images per request is configured by `static/data/frontend_config.json` (`maxBatchImages`) and enforced server-side.

## API schema and examples

- OpenAPI schema: [docs/openapi.yaml](docs/openapi.yaml)
- Generated examples:
  - [docs/examples/validate-request.json](docs/examples/validate-request.json)
  - [docs/examples/validate-response.json](docs/examples/validate-response.json)
  - [docs/examples/batch-response.json](docs/examples/batch-response.json)

Regenerate examples:

- `python scripts/generate_api_examples.py`

## Docs

- Architecture: [docs/architecture.md](docs/architecture.md)
- API schema: [docs/openapi.yaml](docs/openapi.yaml)
- API examples: [docs/examples/validate-request.json](docs/examples/validate-request.json), [docs/examples/validate-response.json](docs/examples/validate-response.json), [docs/examples/batch-response.json](docs/examples/batch-response.json)

## OCR dependency

OCR endpoints require:

- Python deps (`pillow`, `pytesseract`)
- Tesseract binary on host PATH

If Tesseract is unavailable, OCR endpoints return HTTP `503`.

## Deployment

- CI workflow: [.github/workflows/ci.yml](.github/workflows/ci.yml)
- Azure deployment workflow: [.github/workflows/main_ttblabelverifyer.yml](.github/workflows/main_ttblabelverifyer.yml)

Azure deployment strategy:

- Build a Docker image from [Dockerfile](Dockerfile) (includes `tesseract-ocr`).
- Push image to Azure Container Registry (ACR).
- Configure Azure Web App to run that container image.

Required GitHub secrets for container deploy workflow:

- `AZUREAPPSERVICE_CLIENTID_393A544A81EC40399C46C84245657BAF`
- `AZUREAPPSERVICE_TENANTID_F205CD6376B945618A52C395EE12A910`
- `AZUREAPPSERVICE_SUBSCRIPTIONID_5C18393017824C0994DC52BD46394808`
- `AZURE_ACR_NAME`
- `AZURE_RESOURCE_GROUP`

## Known Issues
- Many requirments from TBB are not upheld
- OCR is not great at detecting text in images especailly the goverment warning
- APIs are not encrypted

## Improvements
- Integrating custom tensorflow model could improve OCR accuracy and speed.
- Autehtication and privlege management and integration into user manamegent server.
- MCP server to pull requirments from TBB database would allow independant agents to implement and validate complete requirments. 
- Client facing app to validate before submitting could help breweries / distileries make sure their labels follow the requirments. 
