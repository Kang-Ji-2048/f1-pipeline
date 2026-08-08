# F1 Pipeline — CV Alignment Design

**Date:** 2026-08-08
**Status:** Approved (design), pending spec review
**Author:** Kang Ji

## Goal

Make every phrase in the target CV bullet literally true and defensible under
interview questioning. Nothing faked, nothing stubbed to look real.

Target bullet:

> - Designed and built a real-time ETL pipeline in Python ingesting live telemetry
>   and race data from the OpenF1 and Ergast APIs into a PostgreSQL database for
>   historical and live analysis
> - Automated data ingestion and transformation workflows with GitHub Actions
>   CI/CD, containerised with Docker and deployed on AWS (EC2, S3)
> - Created interactive dashboards to visualise driver performance metrics,
>   lap-time distributions and race strategy patterns

## Current reality (gap analysis)

| Claim | Status before this work |
|-------|-------------------------|
| Python ETL, OpenF1 + Ergast → PostgreSQL | ✅ Real and solid |
| GitHub Actions CI/CD | ✅ Real (lint → test → deploy jobs) |
| Ingests telemetry + race data | ✅ Real, but batch (weekly cron) |
| "real-time / live" analysis | ❌ Scheduled batch only |
| Containerised with Docker | ❌ No Dockerfile / compose |
| Deployed on AWS (EC2, S3) | ❌ No AWS code at all |
| Interactive dashboards | ❌ No dashboard, no viz deps |

Four workstreams close the four gaps. The existing ingestion, schema, validators,
`F1Database` query layer, tests and CI are kept and built upon — not rewritten.

## Constraints

- Keep `mypy --strict`, `ruff check`, `ruff format --check`, and the pytest suite
  green throughout.
- Do not modify existing `#` comments (per repo CLAUDE.md).
- TDD: tests before implementation for all new logic.
- AWS deploy is executed by the user against their own account; this project only
  makes it deployment-ready (code + IaC/scripts + runbook). No credentials are
  ever entered by the assistant.
- New heavy dependencies go behind optional extras so the core pipeline install
  stays lean.

## Workstream 1 — Interactive dashboard

**Closes:** "Created interactive dashboards to visualise driver performance
metrics, lap-time distributions and race strategy patterns."

**Tech:** Streamlit + Plotly, added under a new `[dashboard]` extra.

**Structure:** `src/dashboard/app.py` (entry) with a multi-page/tab layout. All
data access goes through the existing `F1Database` read interface — no raw SQL in
the dashboard. Where a needed aggregation is missing, add a method to
`src/db/queries.py` (e.g. lap-time distribution rows, stint/strategy rows) rather
than querying inline.

Three views, worded to match the bullet:

1. **Driver performance metrics** — season selector; points progression and
   finishing-position trend per driver (built on `get_driver_standings` /
   `get_race_results`).
2. **Lap-time distributions** — race selector; box/violin plot of lap times per
   driver (built on `get_lap_times`, parsing `time_str`/`time_millis`).
3. **Race strategy patterns** — race selector; pit-stop timing and stint-length
   chart per driver (built on `get_pit_stops` + `get_lap_times`).

**Run:** `streamlit run src/dashboard/app.py`, reading `DATABASE_URL` from the
same config. Also exposed as a `docker compose` service.

**Testing:** unit-test any new `queries.py` methods and any lap-time parsing /
stint-derivation helpers (pure functions, no Streamlit runtime in tests).

## Workstream 2 — Docker

**Closes:** "containerised with Docker."

- `Dockerfile` — multi-stage, slim Python 3.11 base, installs the package,
  entrypoint is the `f1-pipeline` CLI.
- `docker-compose.yml` — three services: `db` (postgres:16), `pipeline`
  (runs migrations + ingest), `dashboard` (Streamlit on a published port),
  wired by `DATABASE_URL`. `docker compose up` yields a working local stack.
- `.dockerignore`.

**Testing:** a smoke check that the image builds and `f1-pipeline --help` runs is
documented; not run in unit tests (kept out of the fast pytest path).

## Workstream 3 — Real-time / live ingestion

**Closes:** "real-time … live telemetry … for … live analysis."

- New OpenF1 client method for the latest-data endpoint(s) (e.g. `session_key=latest`
  and incremental `car_data` / laps), added to `src/api/openf1.py`.
- New ingest function `ingest_live(...)` in `src/pipeline/ingest.py` that runs a
  polling loop on a configurable interval, upserting new telemetry/laps as a
  session progresses. Reuses the existing idempotent `_upsert_batch`, so repeated
  polls never duplicate.
- New CLI command `f1-pipeline live` (options: `--session-key` defaulting to
  `latest`, `--interval`, `--max-iterations` for bounded/testable runs).
- Config additions: `LIVE_POLL_INTERVAL` (default e.g. 5s), behind existing
  `Settings`.

**Testing:** the polling loop is tested with a mocked client over a bounded number
of iterations, asserting incremental upserts and clean stop. No real network in
tests (consistent with existing `test_api_clients.py` / `test_ingest.py`).

## Workstream 4 — AWS deployment-ready

**Closes:** "deployed on AWS (EC2, S3)."

- **S3:** `boto3` under a new `[aws]` extra. New `f1-pipeline export-s3` command
  that serialises pipeline outputs (e.g. per-run CSV/parquet exports + the run
  log) and uploads them to a configured bucket/prefix. Config:
  `S3_BUCKET`, `S3_PREFIX`, standard AWS env/role credential resolution.
- **EC2:** `deploy/` directory containing:
  - `deploy/README.md` — step-by-step runbook the user follows to deploy to their
    own EC2 (provision, install Docker, pull repo, set `.env`, `docker compose up`,
    schedule ingest via cron/systemd).
  - `deploy/user-data.sh` — EC2 bootstrap script (installs Docker + compose, clones
    repo, brings the stack up).
  - `.env.example` extended with the new S3/live variables.
- **CI:** extend the existing scheduled `deploy` job to optionally run
  `export-s3` when AWS credentials are present as GitHub secrets (guarded so the
  job still passes without them).

**Testing:** `export-s3` upload logic tested against a mocked `boto3` client
(no real AWS calls). The EC2 runbook is documentation, verified by the user's one
real deploy.

## Cross-cutting deliverables

- Update `README.md` to describe the now-true architecture (dashboard, Docker,
  live mode, AWS) — replacing aspirational roadmap wording with what exists.
- Extend `.env.example` and the config table for all new variables.
- Delete the stray local `master` branch (leftover; not on remote).

## Out of scope (YAGNI)

- No Terraform/CloudFormation full IaC — a bootstrap script + runbook is enough to
  make the deploy real and repeatable without over-engineering.
- No auth/multi-user layer on the dashboard.
- No streaming infrastructure (Kafka/Kinesis) — polling OpenF1's live endpoints is
  the honest, accurate meaning of "real-time" for this data source.
- No predictive fantasy model (separate future project).

## Definition of done

- All four gaps closed with working, tested code.
- `docker compose up` brings up db + pipeline + dashboard locally.
- `f1-pipeline live` performs a real incremental poll-and-upsert.
- Dashboard renders all three views against ingested data.
- `export-s3` uploads artifacts (verified via mock in tests; live during user deploy).
- CI green; README accurate.
- User completes one real EC2/S3 deploy following `deploy/README.md`.
