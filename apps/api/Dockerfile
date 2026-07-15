FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app:/app/apps/api

WORKDIR /app

# System deps for psycopg/pillow/imagehash
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev libjpeg-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy source first so the editable install can find the `app` package.
# (compose also bind-mounts these paths for hot reload.)
COPY apps/api /app/apps/api
COPY services /app/services
COPY packages/policies /app/packages/policies
COPY fixtures /app/fixtures

RUN pip install --upgrade pip && pip install -e "/app/apps/api[dev]"

WORKDIR /app/apps/api
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
