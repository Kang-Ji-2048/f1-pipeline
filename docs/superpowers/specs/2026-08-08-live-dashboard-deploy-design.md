# Live Ingestion, Dashboard & Deployment — Design

**Date:** 2026-08-08
**Status:** Approved (design)
**Author:** Kang Ji

## Goal

Extend the existing batch F1 pipeline into a fuller, production-style system:
real-time (live-polling) ingestion, an interactive analytics dashboard, Docker
containerisation, and AWS (EC2/S3) deployment readiness — building on the
current ingestion, schema, validators, query layer, tests and CI rather than
rewriting them.

## Current vs. target

| Capability | Current | Target |
|-----------|---------|--------|
| Python ETL, OpenF1 + Ergast → PostgreSQL | ✅ | ✅ |
| GitHub Actions CI/CD | ✅ | ✅ |
| Telemetry + race ingestion | ✅ batch (weekly cron) | + live-polling mode |
| Real-time / live analysis | ❌ | ✅ live-polling ingest |
| Containerised with Docker | ❌ | ✅ Dockerfile + compose |
| AWS (EC2, S3) deployment | ❌ | ✅ deployment-ready + runbook |
| Interactive dashboard | ❌ | ✅ Streamlit, three views |

## Constraints

- Keep `mypy --strict`, `ruff check`, `ruff format --check`, and pytest green.
- Do not modify existing `#` comments (per repo CLAUDE.md).
- TDD: tests before implementation for all new logic.
- AWS deploy is executed by the operator against their own account; this project
  only makes it deployment-ready (code + scripts + runbook). No credentials are
  handled in code.
- New heavy dependencies go behind optional extras so the core install stays lean.

## Workstream 1 — Interactive dashboard

**Tech:** Streamlit + Plotly, under a new `[dashboard]` extra.

`src/dashboard/app.py` with a tabbed layout, all data access through the existing
`F1Database` read interface (no raw SQL in the dashboard). Missing aggregations
are added to `src/db/queries.py`.

Three views:

1. **Driver performance metrics** — points progression and finishing-position
   trend per driver/season.
2. **Lap-time distributions** — box/violin plot of lap times per driver for a race.
3. **Race strategy patterns** — pit-stop timing and stint-length chart per driver.

Run: `streamlit run src/dashboard/app.py`; also a `docker compose` service.
Testing: unit-test new `queries.py` methods and any pure parsing/derivation
helpers.

## Workstream 2 — Docker

- `Dockerfile` — multi-stage, slim Python 3.11, entrypoint the `f1-pipeline` CLI.
- `docker-compose.yml` — `db` (postgres:16), `pipeline` (schema init + ingest),
  `dashboard` (Streamlit), wired by `DATABASE_URL`.
- `.dockerignore`.

## Workstream 3 — Real-time / live ingestion

- New OpenF1 client method for the latest-data endpoint (`session_key=latest`,
  incremental `date>` filter).
- `ingest_live(...)` polling loop in `src/pipeline/ingest.py`, reusing the
  idempotent `_upsert_batch` so repeated polls never duplicate.
- CLI command `f1-pipeline live` (`--session-key`, `--interval`, `--max-iterations`).
- Config: `LIVE_POLL_INTERVAL`.
- Testing: mocked client over bounded iterations, asserting incremental upserts.

## Workstream 4 — AWS deployment-ready

- **S3:** `boto3` under an `[aws]` extra; `f1-pipeline export-s3` serialises run
  outputs to CSV and uploads to a configured bucket/prefix.
- **EC2:** a `deploy/` directory with a runbook (`deploy/README.md`) and an EC2
  bootstrap script (`deploy/user-data.sh`).
- **CI:** extend the scheduled `deploy` job to optionally run `export-s3` when AWS
  secrets are present (guarded so CI still passes without them).
- Testing: `export-s3` upload logic tested against a mocked `boto3` client.

## Cross-cutting

- Update `README.md` to describe the extended architecture.
- Extend `.env.example` and the config table for new variables.

## Out of scope (YAGNI)

- No full IaC (Terraform/CloudFormation) — a bootstrap script + runbook suffices.
- No auth/multi-user layer on the dashboard.
- No streaming infrastructure (Kafka/Kinesis) — polling OpenF1's live endpoints is
  the appropriate meaning of "real-time" for this source.
- No predictive modelling (separate future project).

## Definition of done

- All four workstreams delivered with working, tested code.
- `docker compose up` brings up db + pipeline + dashboard locally.
- `f1-pipeline live` performs a real incremental poll-and-upsert.
- Dashboard renders all three views against ingested data.
- `export-s3` uploads artifacts (verified via mock in tests; live during deploy).
- CI green; README accurate.
