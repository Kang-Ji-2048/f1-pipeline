"""Core ingestion logic with idempotent upserts and batch processing."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from typing import Any

import structlog
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.api.ergast import ErgastClient
from src.api.openf1 import OpenF1Client
from src.config import settings
from src.db.engine import get_session
from src.db.schema import (
    Base,
    Circuit,
    Constructor,
    Driver,
    LapTime,
    PitStop,
    Race,
    RaceResult,
    Season,
    SessionInfo,
    TelemetrySample,
)

logger = structlog.get_logger(__name__)


# ── Generic upsert helper ────────────────────────────────────────────────────


def _upsert_batch(
    session: Session,
    model: type[Base],
    rows: list[dict[str, Any]],
    conflict_columns: list[str],
) -> int:
    """Perform a batched idempotent upsert using ON CONFLICT DO UPDATE."""
    if not rows:
        return 0

    mapper = sa_inspect(model)
    update_cols = [
        c.key for c in mapper.column_attrs if c.key not in conflict_columns and c.key != "id"
    ]

    total = 0
    for i in range(0, len(rows), settings.BATCH_SIZE):
        batch = rows[i : i + settings.BATCH_SIZE]
        stmt = pg_insert(model).values(batch)
        if update_cols:
            stmt = stmt.on_conflict_do_update(
                index_elements=conflict_columns,
                set_={col: stmt.excluded[col] for col in update_cols},
            )
        else:
            stmt = stmt.on_conflict_do_nothing(index_elements=conflict_columns)
        session.execute(stmt)
        total += len(batch)
    session.flush()
    logger.info("upserted", model=model.__tablename__, count=total)
    return total


# ── Ergast ingestion ──────────────────────────────────────────────────────────


def ingest_season(season_year: int) -> dict[str, int]:
    """Ingest a full season of Ergast data. Returns row counts per table."""
    counts: dict[str, int] = {}

    with ErgastClient() as ergast, get_session() as session:
        # Season
        _upsert_batch(session, Season, [{"year": season_year}], ["year"])
        counts["seasons"] = 1

        # Drivers
        drivers = ergast.get_drivers(season_year)
        counts["drivers"] = _upsert_batch(
            session,
            Driver,
            [d.model_dump(by_alias=False) for d in drivers],
            ["driver_ref"],
        )

        # Constructors
        constructors = ergast.get_constructors(season_year)
        counts["constructors"] = _upsert_batch(
            session,
            Constructor,
            [c.model_dump(by_alias=False) for c in constructors],
            ["constructor_ref"],
        )

        # Circuits
        circuits = ergast.get_circuits(season_year)
        counts["circuits"] = _upsert_batch(
            session,
            Circuit,
            [c.model_dump(by_alias=False) for c in circuits],
            ["circuit_ref"],
        )

        # Races
        races = ergast.get_races(season_year)
        race_rows = []
        for r in races:
            race_rows.append(
                {
                    "season_year": r.season,
                    "round": r.round,
                    "name": r.race_name,
                    "circuit_ref": r.circuit.circuit_ref,
                    "date": r.date,
                    "time": r.time,
                    "url": r.url,
                }
            )
        counts["races"] = _upsert_batch(session, Race, race_rows, ["season_year", "round"])

        # Build race ID lookup
        race_id_map = _build_race_id_map(session, season_year)

        # Per-race detail data
        result_count = 0
        lap_count = 0
        pit_count = 0

        for race in races:
            race_id = race_id_map.get((season_year, race.round))
            if race_id is None:
                continue

            # Results
            results = ergast.get_results(season_year, race.round)
            result_rows = []
            for res in results:
                result_rows.append(
                    {
                        "race_id": race_id,
                        "driver_ref": res.driver.driver_ref,
                        "constructor_ref": res.constructor.constructor_ref,
                        "grid": res.grid,
                        "position": res.position,
                        "position_text": res.position_text,
                        "points": res.points,
                        "laps": res.laps,
                        "status": res.status,
                        "time_millis": res.time_millis,
                        "fastest_lap_rank": res.fastest_lap_rank,
                        "fastest_lap_time": res.fastest_lap_time,
                        "fastest_lap_speed": res.fastest_lap_speed,
                    }
                )
            result_count += _upsert_batch(
                session, RaceResult, result_rows, ["race_id", "driver_ref"]
            )

            # Lap times
            laps = ergast.get_lap_times(season_year, race.round)
            lap_rows = [
                {
                    "race_id": race_id,
                    "driver_ref": lt.driver_ref,
                    "lap": lt.lap,
                    "position": lt.position,
                    "time_str": lt.time_str,
                }
                for lt in laps
            ]
            lap_count += _upsert_batch(session, LapTime, lap_rows, ["race_id", "driver_ref", "lap"])

            # Pit stops
            pit_stops = ergast.get_pit_stops(season_year, race.round)
            pit_rows = [
                {
                    "race_id": race_id,
                    "driver_ref": ps.driver_ref,
                    "stop": ps.stop,
                    "lap": ps.lap,
                    "time_of_day": ps.time_of_day,
                }
                for ps in pit_stops
            ]
            pit_count += _upsert_batch(
                session, PitStop, pit_rows, ["race_id", "driver_ref", "stop"]
            )

        counts["race_results"] = result_count
        counts["lap_times"] = lap_count
        counts["pit_stops"] = pit_count

    logger.info("season_ingested", season=season_year, counts=counts)
    return counts


# ── OpenF1 ingestion ─────────────────────────────────────────────────────────


def ingest_telemetry(
    year: int,
    session_keys: Sequence[int] | None = None,
    skip_existing: bool = False,
) -> dict[str, int]:
    """Ingest OpenF1 session and telemetry data for a year.

    Telemetry is fetched one driver at a time (an entire session's ``car_data`` is
    far too large for a single request), and progress is committed after each
    session so a failure part-way leaves the completed sessions persisted. Pass
    ``skip_existing=True`` to resume: sessions that already have telemetry rows are
    skipped instead of re-fetched.
    """
    counts: dict[str, int] = {}

    with OpenF1Client() as openf1, get_session() as session:
        sessions = openf1.get_sessions(year)
        session_rows = [s.model_dump() for s in sessions]
        counts["sessions"] = _upsert_batch(session, SessionInfo, session_rows, ["session_key"])
        session.commit()

        keys = list(session_keys) if session_keys else [s.session_key for s in sessions]

        if skip_existing:
            done = {row[0] for row in session.query(TelemetrySample.session_key).distinct().all()}
            keys = [k for k in keys if k not in done]

        telem_count = 0
        for sk in keys:
            session_total = 0
            for driver_number in openf1.get_session_drivers(sk):
                samples = openf1.get_car_data(sk, driver_number=driver_number)
                telem_rows = [t.model_dump() for t in samples]
                session_total += _upsert_batch(
                    session,
                    TelemetrySample,
                    telem_rows,
                    ["session_key", "driver_number", "date"],
                )
            session.commit()
            telem_count += session_total
            logger.info("session_telemetry_ingested", session_key=sk, count=session_total)
        counts["telemetry_samples"] = telem_count

    logger.info("telemetry_ingested", year=year, counts=counts)
    return counts


def ingest_live(
    session_key: int | str = "latest",
    interval: float = 5.0,
    max_iterations: int | None = None,
    client: OpenF1Client | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, int]:
    """Poll OpenF1 for live telemetry and upsert new samples incrementally.

    Each iteration fetches only samples newer than the highest ``date`` seen so
    far (a moving cursor), so repeated polls never re-ingest the same rows. Runs
    until ``max_iterations`` is reached, or forever when it is ``None``.

    ``client`` and ``sleep`` are injectable for testing; an internally-created
    client is closed on exit, an injected one is left to the caller.
    """
    counts: dict[str, int] = {"telemetry_samples": 0, "iterations": 0}
    own_client = client is None
    openf1 = client or OpenF1Client()
    after: str | None = None

    try:
        with get_session() as session:
            iteration = 0
            while max_iterations is None or iteration < max_iterations:
                samples = openf1.get_latest_car_data(session_key, after=after)
                if samples:
                    rows = [s.model_dump() for s in samples]
                    counts["telemetry_samples"] += _upsert_batch(
                        session,
                        TelemetrySample,
                        rows,
                        ["session_key", "driver_number", "date"],
                    )
                    after = max(s.date for s in samples).isoformat()
                counts["iterations"] += 1
                iteration += 1
                logger.info(
                    "live_poll",
                    session_key=session_key,
                    new_samples=len(samples),
                    cursor=after,
                )
                if max_iterations is None or iteration < max_iterations:
                    sleep(interval)
    finally:
        if own_client:
            openf1.close()

    logger.info("live_ingest_stopped", session_key=session_key, counts=counts)
    return counts


# ── Helpers ───────────────────────────────────────────────────────────────────


def _build_race_id_map(session: Session, season_year: int) -> dict[tuple[int, int], int]:
    races = (
        session.query(Race.id, Race.season_year, Race.round)
        .filter(Race.season_year == season_year)
        .all()
    )
    return {(r.season_year, r.round): r.id for r in races}
