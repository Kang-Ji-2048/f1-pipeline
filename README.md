# F1 Data Pipeline

An end-to-end, production-style data pipeline that ingests Formula 1 telemetry, timing, and results from the **Ergast** and **OpenF1** APIs into a normalised **PostgreSQL** database. Built with typed models, schema migrations, retry-resilient API clients, automated tests, and CI — and, admittedly, to give me an edge in F1 fantasy. 🏎️

## Highlights

- **Two data sources, one schema** — Ergast for historical data (all seasons), OpenF1 for high-precision data from 2023 onward, reconciled into a single normalised model.
- **Idempotent by design** — every fact table uses composite unique constraints, so re-running the pipeline upserts rather than duplicates.
- **Resilient ingestion** — HTTP clients use exponential-backoff retries (Tenacity) and structured logging (structlog).
- **Validated at the boundary** — incoming records are parsed and validated with Pydantic before they ever reach the database.
- **Migrations, not guesswork** — schema is versioned with Alembic.
- **Tested and linted in CI** — GitHub Actions runs ruff, `mypy --strict`, and the pytest suite on every push/PR.

## Architecture

```
Ergast / OpenF1 API  ->  API clients (httpx + retries)  ->  Pydantic validators  ->  SQLAlchemy upserts  ->  PostgreSQL
```

## Tech stack

| Layer | Tools |
|-------|-------|
| Language | Python 3.11+ |
| HTTP | httpx, Tenacity (retries) |
| Data modelling | Pydantic v2 |
| Database | PostgreSQL, SQLAlchemy 2.0, Alembic (migrations) |
| CLI | Click |
| Logging | structlog |
| Quality | pytest + pytest-cov, ruff, mypy (strict) |
| CI | GitHub Actions |

## Database schema

Normalised into dimension and fact tables:

- **Dimensions:** `seasons`, `circuits`, `drivers`, `constructors`
- **Facts:** `races`, `race_results`, `lap_times`, `pit_stops`
- **Telemetry:** `sessions`, `telemetry_samples`

All fact tables use composite unique constraints for idempotent upserts.

## Getting started

```bash
# 1. Install (dev extras include pytest, ruff, mypy)
pip install -e ".[dev]"

# 2. Configure (copy and edit)
cp .env.example .env

# 3. Apply database migrations
alembic upgrade head

# 4. Run the pipeline
f1-pipeline            # or: python run.py
```

## Configuration

Set via environment variables or a `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://f1user:f1pass@localhost:5432/f1data` | PostgreSQL connection string |
| `BATCH_SIZE` | `500` | Rows per upsert batch |
| `MAX_RETRIES` | `3` | HTTP retry attempts |
| `RETRY_BACKOFF` | `2.0` | Exponential backoff multiplier |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

## Testing

```bash
pytest                 # unit tests
pytest -m integration  # tests that require a live database
```

## Notes

- Ergast is officially deprecated but remains the source for historical data; a drop-in replacement is available at `api.jolpi.ca/ergast/`.

## Roadmap

- Feed the pipeline output directly into a predictive model for F1 fantasy team selection.
