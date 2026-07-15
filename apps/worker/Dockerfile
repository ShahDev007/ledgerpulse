FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app:/app/apps/api:/app/apps/worker

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev libjpeg-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Worker reuses the API's domain/model code + shared services. Copy source before install.
COPY apps/worker /app/apps/worker
COPY apps/api /app/apps/api
COPY services /app/services
COPY packages/policies /app/packages/policies
COPY fixtures /app/fixtures

RUN pip install --upgrade pip && pip install -e /app/apps/worker && pip install -e /app/apps/api

CMD ["celery", "-A", "worker.celery_app.app", "worker", "--loglevel=info", "--concurrency=4"]
