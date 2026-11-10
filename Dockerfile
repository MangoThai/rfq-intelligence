# syntax=docker/dockerfile:1

# Stage 1 — Builder
FROM python:3.13.18-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /uvx /bin/

WORKDIR /app

ENV UV_PYTHON_DOWNLOADS=0 \
    UV_NO_DEV=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./

RUN uv sync \
    --frozen \
    --no-dev \
    --no-install-project

COPY README.md ./
COPY src ./src

RUN uv sync \
    --frozen \
    --no-dev \
    --no-editable


# Stage 2 — Runtime
FROM python:3.13.18-slim-bookworm AS runtime

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    RFQ_DATA_DIR="/app/data"

RUN groupadd --system app \
    && useradd \
    --system \
    --gid app \
    --create-home \
    app

COPY --from=builder \
    --chown=app:app \
    /app/.venv \
    /app/.venv

COPY --chown=app:app data ./data
COPY --chown=app:app alembic.ini /app/alembic.ini
COPY --chown=app:app alembic /app/alembic


USER app

EXPOSE 8000

HEALTHCHECK \
    --interval=30s \
    --timeout=3s \
    --start-period=5s \
    --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).read()"]

CMD ["uvicorn", "rfq_intelligence.main:app", "--host", "0.0.0.0", "--port", "8000"]