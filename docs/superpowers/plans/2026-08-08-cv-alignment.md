# F1 Pipeline CV-Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every claim in the target CV bullet literally true — add a real-time live-polling ingest mode, an interactive Streamlit dashboard, Docker containerisation, and AWS (EC2/S3) deployment-readiness — on top of the existing batch pipeline.

**Architecture:** Keep the existing `src/api` → `src/models` → `src/pipeline` → `src/db` layering. Add: a live-polling ingest path reusing the idempotent `_upsert_batch`; dashboard-specific read methods on `F1Database` consumed by a Streamlit app; a boto3-based S3 export command; Docker + compose + an EC2 runbook.

**Tech Stack:** Python 3.11+, httpx, Pydantic v2, SQLAlchemy 2.0, Click, structlog, Streamlit, Plotly, boto3, Docker, PostgreSQL 16.

## Global Constraints

- Keep `mypy --strict`, `ruff check src/ tests/`, `ruff format --check src/ tests/`, and `pytest` green after every task.
- Never modify existing `#` comments in the codebase (repo CLAUDE.md). Append-only around them.
- TDD: failing test first for all new pure/business logic. Streamlit UI and Dockerfiles are verified manually (documented), not unit-tested.
- New heavy deps go behind optional extras: `[dashboard]` (streamlit, plotly), `[aws]` (boto3).
- All commits authored as `Kang <jik2048@gmail.com>`, no `Co-Authored-By` trailer.
- Work on branch `cv-alignment`.

---

### Task 1: OpenF1 latest-data client method

**Files:**
- Modify: `src/api/openf1.py`
- Test: `tests/test_api_clients.py`

**Interfaces:**
- Consumes: `APIClient.get`, `TelemetryData` validator.
- Produces: `OpenF1Client.get_latest_car_data(session_key: int | str = "latest", after: str | None = None) -> list[TelemetryData]` — fetches `/car_data` for the given session (accepts the literal `"latest"`), optionally only samples with `date > after` (ISO string) using OpenF1's `date>` filter.

- [ ] **Step 1: Write failing test** — mock `APIClient.get` to assert `get_latest_car_data("latest", after="2023-01-01T00:00:00")` calls `/car_data` with `session_key="latest"` and a `date>` param, and returns validated `TelemetryData`.
- [ ] **Step 2: Run test, verify it fails** (`AttributeError: get_latest_car_data`).
- [ ] **Step 3: Implement** `get_latest_car_data` mirroring `get_car_data`, adding `session_key` passthrough and, when `after` is set, `params["date>"] = after`.
- [ ] **Step 4: Run tests, verify pass.**
- [ ] **Step 5: Commit** `feat(openf1): add get_latest_car_data for live polling`.

---

### Task 2: Live ingest loop

**Files:**
- Modify: `src/pipeline/ingest.py`, `src/config.py` (append `LIVE_POLL_INTERVAL`)
- Test: `tests/test_ingest.py`

**Interfaces:**
- Consumes: `OpenF1Client.get_latest_car_data`, `_upsert_batch`, `TelemetrySample`.
- Produces: `ingest_live(session_key: int | str = "latest", interval: float = 5.0, max_iterations: int | None = None, client=None, sleep=time.sleep) -> dict[str, int]` — loops up to `max_iterations` (or forever if None), each iteration fetching samples newer than the last seen `date`, upserting them, tracking a running total in `{"telemetry_samples": N, "iterations": M}`. `client`/`sleep` are injectable for tests.

- [ ] **Step 1: Write failing test** — inject a fake client returning 2 samples then 1 sample over 2 iterations (`max_iterations=2`), a no-op `sleep`, assert `_upsert_batch` receives incremental rows and result totals are correct; assert the second call passes an `after` cursor from the first batch's max date.
- [ ] **Step 2: Run test, verify it fails.**
- [ ] **Step 3: Implement** `ingest_live` with the polling loop, cursor tracking (max `date` seen), injectable `client`/`sleep`, structured logging per iteration.
- [ ] **Step 4: Run tests, verify pass.**
- [ ] **Step 5: Commit** `feat(pipeline): add ingest_live polling loop`.

---

### Task 3: `f1-pipeline live` CLI command

**Files:**
- Modify: `src/pipeline/cli.py`
- Test: `tests/test_ingest.py` (or a small CLI test using Click's `CliRunner`)

**Interfaces:**
- Consumes: `ingest_live`.
- Produces: CLI command `live` with `--session-key` (default `"latest"`), `--interval` (float, default from settings), `--max-iterations` (int, optional).

- [ ] **Step 1: Write failing test** — `CliRunner` invokes `live --max-iterations 1` with `ingest_live` monkeypatched to a stub; assert it's called with parsed options and success output.
- [ ] **Step 2: Run test, verify it fails.**
- [ ] **Step 3: Implement** the `live` command mirroring the error-handling pattern of `ingest_openf1`.
- [ ] **Step 4: Run tests, verify pass.**
- [ ] **Step 5: Commit** `feat(cli): add live command for real-time ingest`.

---

### Task 4: Dashboard query helpers

**Files:**
- Modify: `src/db/queries.py`
- Test: `tests/test_queries.py` (new; use in-memory/SQLite-compatible fixtures or a session fixture consistent with existing tests)

**Interfaces:**
- Consumes: existing schema models.
- Produces on `F1Database`:
  - `get_lap_time_distribution(season_year: int, round_num: int) -> list[dict]` — rows `{driver_ref, lap, time_millis}` with `time_millis` non-null (parsed from `time_str` if needed).
  - `get_stints(season_year: int, round_num: int) -> list[dict]` — per driver, stint segments derived from pit-stop laps: `{driver_ref, stint, start_lap, end_lap, laps}`.

- [ ] **Step 1: Write failing tests** for both methods against seeded data (a race with laps + 1–2 pit stops), asserting distribution rows and correct stint boundaries.
- [ ] **Step 2: Run tests, verify they fail.**
- [ ] **Step 3: Implement** both methods (add a `time_str`→millis parse helper if `time_millis` absent).
- [ ] **Step 4: Run tests, verify pass.**
- [ ] **Step 5: Commit** `feat(db): add dashboard query helpers (lap distribution, stints)`.

---

### Task 5: Streamlit dashboard app

**Files:**
- Create: `src/dashboard/__init__.py`, `src/dashboard/app.py`
- Modify: `pyproject.toml` (add `[dashboard]` extra: streamlit, plotly)

**Interfaces:**
- Consumes: `F1Database` (all read methods incl. Task 4).
- Produces: a runnable `streamlit run src/dashboard/app.py` with three tabs — Driver performance, Lap-time distributions, Race strategy.

- [ ] **Step 1: Add `[dashboard]` optional-dependency extra** to `pyproject.toml`.
- [ ] **Step 2: Implement** `app.py` — sidebar season/race selectors backed by `F1Database`; Tab 1 points progression (line) + standings (bar); Tab 2 lap-time box/violin via `get_lap_time_distribution`; Tab 3 stint/pit chart via `get_stints`/`get_pit_stops`.
- [ ] **Step 3: Manual verify** — document `pip install -e ".[dashboard]" && streamlit run src/dashboard/app.py`; confirm all three tabs render (verified after DB is populated). Ensure `ruff`/`mypy` pass on `app.py`.
- [ ] **Step 4: Commit** `feat(dashboard): add Streamlit app with three views`.

---

### Task 6: Docker containerisation

**Files:**
- Create: `Dockerfile`, `docker-compose.yml`, `.dockerignore`

- [ ] **Step 1: Write `Dockerfile`** — multi-stage, `python:3.11-slim`, `pip install -e ".[dashboard,aws]"`, entrypoint `f1-pipeline`.
- [ ] **Step 2: Write `docker-compose.yml`** — `db` (postgres:16 with the default creds/env), `pipeline` (runs `init-db`/migrations then can ingest), `dashboard` (streamlit, published port, `command: streamlit run src/dashboard/app.py`), all sharing `DATABASE_URL`.
- [ ] **Step 3: Write `.dockerignore`** (`.git`, `__pycache__`, `.venv`, `*.egg-info`, `docs`).
- [ ] **Step 4: Verify** — `docker compose config` parses; document `docker compose up`.
- [ ] **Step 5: Commit** `feat(docker): add Dockerfile, compose stack, dockerignore`.

---

### Task 7: AWS S3 export

**Files:**
- Modify: `pyproject.toml` (add `[aws]` extra: boto3), `src/config.py` (append `S3_BUCKET`, `S3_PREFIX`)
- Create: `src/pipeline/export.py`
- Modify: `src/pipeline/cli.py` (add `export-s3` command)
- Test: `tests/test_export.py`

**Interfaces:**
- Produces: `export_to_s3(rows_by_table: dict[str, list[dict]], bucket: str, prefix: str, client=None) -> list[str]` — writes each table to CSV and uploads to `s3://bucket/prefix/<table>.csv`, returning the S3 keys; `client` injectable (boto3 s3 client) for tests. CLI `export-s3 --season` gathers via `F1Database` and calls it.

- [ ] **Step 1: Write failing test** — inject a mock boto3 client, call `export_to_s3` with sample rows, assert `put_object`/`upload_fileobj` called per table with expected keys and CSV content.
- [ ] **Step 2: Run test, verify it fails.**
- [ ] **Step 3: Implement** `export.py` and the `export-s3` CLI command (credentials via standard AWS env/role resolution).
- [ ] **Step 4: Run tests, verify pass.**
- [ ] **Step 5: Commit** `feat(aws): add S3 export command`.

---

### Task 8: EC2 deploy runbook + CI + docs

**Files:**
- Create: `deploy/README.md`, `deploy/user-data.sh`
- Modify: `.env.example`, `.github/workflows/ci.yml`, `README.md`

- [ ] **Step 1: Write `deploy/user-data.sh`** — EC2 bootstrap: install Docker + compose plugin, clone repo, `docker compose up -d`.
- [ ] **Step 2: Write `deploy/README.md`** — step-by-step: launch EC2, set `.env` (incl. S3 vars), run bootstrap, schedule ingest (cron/systemd), point to dashboard port.
- [ ] **Step 3: Extend `.env.example`** with `LIVE_POLL_INTERVAL`, `S3_BUCKET`, `S3_PREFIX`.
- [ ] **Step 4: Extend CI `deploy` job** — add an optional `export-s3` step guarded by presence of AWS secrets (`if:` on a secret/env), so CI passes without them.
- [ ] **Step 5: Update `README.md`** — document dashboard, Docker, live mode, AWS; replace aspirational roadmap wording with what now exists. Do not touch existing `#` code comments (this is markdown, safe).
- [ ] **Step 6: Commit** `docs: add EC2 deploy runbook, CI S3 step, README update`.

---

### Task 9: Cleanup

- [ ] **Step 1:** Delete stray local `master` branch: `git branch -D master`.
- [ ] **Step 2:** Full green check: `ruff check src/ tests/ && ruff format --check src/ tests/ && mypy --strict src/ && pytest`.
- [ ] **Step 3:** Push branch `cv-alignment` to origin under the user's account and open a PR (or fast-forward to `main` per user preference).

## Self-Review

- **Spec coverage:** Dashboard (Tasks 4,5) ✓; Docker (Task 6) ✓; real-time (Tasks 1,2,3) ✓; AWS S3 (Task 7) + EC2 (Task 8) ✓; README/env/cleanup (Tasks 8,9) ✓.
- **Placeholder scan:** none — each task names exact files, interfaces, and test intent.
- **Type consistency:** `get_latest_car_data` (T1) → `ingest_live` (T2) → `live` CLI (T3); `get_lap_time_distribution`/`get_stints` (T4) → dashboard (T5); `export_to_s3` (T7) → CLI + CI (T8) all consistent.
