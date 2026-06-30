# KatılımLens — TEKNOFEST Senaryo 2 (FastAPI backend + statik frontend, tek imaj)
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TF_LLM_PROVIDER=mock

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend /app/backend
COPY frontend /app/frontend

WORKDIR /app/backend

# Render PORT ortam değişkeni verir; yoksa 8090
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8090}
