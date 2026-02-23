#!/usr/bin/env bash
set -euo pipefail

if ! command -v tesseract >/dev/null 2>&1; then
  echo "[startup] tesseract not found; installing..."
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends tesseract-ocr
  rm -rf /var/lib/apt/lists/*
fi

exec gunicorn --bind=0.0.0.0:${PORT:-8000} app:app
