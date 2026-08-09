# F1 Data Pipeline

An end-to-end, production-style data pipeline that ingests Formula 1 telemetry, timing, and results from the **Ergast** and **OpenF1** APIs into a normalised **PostgreSQL** database. Built with typed models, schema migrations, retry-resilient API clients, automated tests, and CI — and, admittedly, to give me an edge in F1 fantasy. 🏎️

## Highlights

- **Two data sources, one schema** — Ergast for historical data (all seasons), OpenF1 for high-precision data from 2023 onward, reconciled into a single normalised model.
- **Batch *and* real-time** — ingest a whole season in one command, or run `f1-pipeline live` to poll OpenF1's latest-data endpoints and upsert telemetry incrementally as a session runs.
- **Idempotent by design** — every fact table uses composite unique constraints, so re-running the pipeline (or polling live) upserts rather than duplicates.
- **Resilient ingestion** — HTTP clients use exponential-backoff retries (Tenacity) and structured logging (structlog).
- **Validated at the boundary** — incoming records are parsed and validated with Pydantic before they ever reach the database.
- **Migrations, not guesswork** — schema is versioned with Alembic.
- **Interactive dashboard** — a Streamlit + Plotly app with nine views: driver and constructor standings, lap-time and pace analysis, race strategy, circuit history, telemetry traces, driver head-to-head, a championship what-if projector, and ML-based points predictions.
- **Predictive modelling** — a leakage-safe scikit-learn model forecasts each driver's race points, evaluated against a baseline on a time-ordered split, and surfaced via both the CLI and a dashboard tab.
- **Analytics layer** — pure, unit-tested functions in [`src/analysis/`](src/analysis) (pace metrics, championship projections) and [`src/ml/`](src/ml) (feature engineering, the points model) kept separate from I/O.
- **Containerised** — `docker compose up` brings up Postgres, the pipeline, and the dashboard together.
- **Deployable** — ships with an EC2 runbook and S3 export for running in AWS (see [`deploy/`](deploy/README.md)).
- **Tested and linted in CI** — GitHub Actions runs ruff, `mypy --strict`, and the pytest suite on every push/PR.

## Architecture

```
Ergast / OpenF1 API  ->  API clients (httpx + retries)  ->  Pydantic validators  ->  SQLAlchemy upserts  ->  PostgreSQL
                                                                                                                 |
                                                                              Streamlit dashboard  <------------ +  ------> S3 export (CSV)
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
| Dashboard | Streamlit, Plotly, pandas |
| ML | scikit-learn, joblib, numpy, pandas |
| Cloud | Docker, docker-compose, AWS (EC2, S3 via boto3) |
| Quality | pytest + pytest-cov, ruff, mypy (strict) |
| CI | GitHub Actions |

## Database schema

Normalised into dimension and fact tables:

- **Dimensions:** `seasons`, `circuits`, `drivers`, `constructors`
- **Facts:** `races`, `race_results`, `lap_times`, `pit_stops`
- **Telemetry:** `sessions`, `telemetry_samples`

All fact tables use composite unique constraints for idempotent upserts.

## Getting started

### Option A — Docker (everything at once)

```bash
docker compose up -d --build          # Postgres + pipeline (schema init) + dashboard
docker compose run --rm pipeline ingest-all --season 2025
# open the dashboard at http://localhost:8501
```

### Option B — Local Python

```bash
# 1. Install (dev extras include pytest, ruff, mypy; add dashboard/aws as needed)
pip install -e ".[dev,dashboard,aws]"

# 2. Configure (copy and edit)
cp .env.example .env

# 3. Apply database migrations
alembic upgrade head

# 4. Run the pipeline
f1-pipeline ingest-all --season 2025  # or: python run.py
```

## Real-time ingestion

Poll OpenF1 during a live session and upsert new telemetry as it arrives:

```bash
f1-pipeline live --session-key latest --interval 5
```

It tracks a moving timestamp cursor, so each poll fetches only newly-arrived
samples and the idempotent upserts never duplicate.

## Dashboard

```bash
pip install -e ".[dashboard]"
streamlit run src/dashboard/app.py
```

Nine views, all reading from the same `DATABASE_URL`:

- **Driver performance** — standings and points progression.
- **Constructors** — team standings and points contribution.
- **Lap-time distributions** — per-driver box plots plus fastest-lap / consistency pace cards.
- **Race strategy** — stint lengths and pit stops.
- **Circuits** — per-circuit history and past winners.
- **Telemetry** — speed / throttle-brake / gear traces per driver from OpenF1.
- **Head-to-head** — compare two drivers across the season.
- **What-if** — championship projection: who can still mathematically win.
- **Predictions** — the ML points model's hold-out quality metrics, feature
  importances, and predicted-vs-actual points per race (needs the `ml` extra).

Read queries are cached (`st.cache_data`) so switching views doesn't re-hit the
database each time.

## Deployment (AWS)

The [`deploy/`](deploy/README.md) directory contains an EC2 bootstrap script and
a step-by-step runbook for running the Docker stack on AWS, plus S3 export:

```bash
f1-pipeline export-s3 --season 2025   # uploads per-table CSVs to s3://$S3_BUCKET/$S3_PREFIX/2025/
```

To redeploy a running instance after merging changes, SSH in and run the update
helper (pull + rebuild + force-recreate) — see the [deploy runbook](deploy/README.md):

```bash
cd /opt/f1-pipeline && sudo bash deploy/update.sh
```

## Predictive model

A gradient-boosting regressor predicts each driver's points for a race from
**leakage-safe** features — qualifying grid position, rolling recent form (points
and finishing position), season-to-date and constructor form, and the driver's
history at that circuit. It is evaluated with a **time-ordered train/test split**
(train on earlier races, test on later ones) against a linear-regression baseline,
reporting MAE, R² and feature importances.

```bash
pip install -e ".[ml]"
f1-pipeline train-model                      # train, evaluate, save to models/
f1-pipeline predict --season 2025 --round 1  # ranked predicted points per driver
```

Feature engineering ([`src/ml/features.py`](src/ml/features.py)) and the model
wrapper ([`src/ml/model.py`](src/ml/model.py)) are separated from I/O and unit
tested without a database.

## Configuration

Set via environment variables or a `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://f1user:f1pass@localhost:5432/f1data` | PostgreSQL connection string |
| `BATCH_SIZE` | `500` | Rows per upsert batch |
| `MAX_RETRIES` | `3` | HTTP retry attempts |
| `RETRY_BACKOFF` | `2.0` | Exponential backoff multiplier |
| `RATE_LIMIT_DELAY` | `0.5` | Minimum seconds between HTTP requests (stays under API rate limits) |
| `LIVE_POLL_INTERVAL` | `5.0` | Default seconds between polls in `live` mode |
| `S3_BUCKET` | _(unset)_ | Target bucket for `export-s3` |
| `S3_PREFIX` | `f1-pipeline` | Key prefix for S3 exports |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

## Testing

```bash
pytest                 # unit tests
pytest -m integration  # tests that require a live database
```

## Notes

- Ergast is officially deprecated but remains the source for historical data; a drop-in replacement is available at `api.jolpi.ca/ergast/`.

## Roadmap

- Persist live telemetry summaries into dedicated dashboard-friendly aggregate tables.
- Backfill multiple seasons to train the points model on a larger history.
