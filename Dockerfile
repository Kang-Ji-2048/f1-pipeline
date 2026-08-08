# syntax=docker/dockerfile:1

# ── Build stage: install the package and its extras into an isolated prefix ──
FROM python:3.11-slim AS builder
ENV PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --upgrade pip \
    && pip install --prefix=/install ".[dashboard,aws]"

# ── Runtime stage: slim image with just the installed deps and the source ──
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY --from=builder /install /usr/local
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini run.py README.md ./

# Default to the CLI; compose overrides this for the dashboard service.
ENTRYPOINT ["f1-pipeline"]
CMD ["--help"]
