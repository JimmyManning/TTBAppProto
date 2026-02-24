FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata \
    OMP_THREAD_LIMIT=1 \
    GUNICORN_TIMEOUT=180 \
    GUNICORN_GRACEFUL_TIMEOUT=30 \
    GUNICORN_WORKERS=1

WORKDIR /app

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng tesseract-ocr-osd \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "gunicorn --bind=0.0.0.0:${PORT:-8000} --workers=${GUNICORN_WORKERS} --timeout=${GUNICORN_TIMEOUT} --graceful-timeout=${GUNICORN_GRACEFUL_TIMEOUT} app:app"]
