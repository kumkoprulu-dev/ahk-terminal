# AHK Terminal — tek imaj (FastAPI backend + statik frontend)
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Bağımlılıklar
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt psycopg2-binary

# Uygulama (backend + frontend)
COPY backend /app/backend
COPY frontend /app/frontend

WORKDIR /app/backend

# Render PORT ortam değişkeni verir; yoksa 8077
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8077}
