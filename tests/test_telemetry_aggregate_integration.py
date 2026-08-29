"""Integration tests for telemetry aggregation (needs a real database).

The aggregation runs a SQL ``GROUP BY`` with conditional averages, so it is
exercised against an actual database rather than a mock. The tests skip cleanly
when no database is reachable (e.g. a local run without Postgres up), and run in
CI where a Postgres service is provided.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from src.config import settings
from src.db.schema import Base, TelemetrySample, TelemetrySummary
from src.pipeline.ingest import aggregate_telemetry

pytestmark = pytest.mark.integration

_SESSION_KEY = 999901  # high, test-only key so we never touch real data


@pytest.fixture()
def db_session():
    """Yield a session against the configured DB, skipping if none is reachable."""
    engine = create_engine(settings.DATABASE_URL)
    try:
        conn = engine.connect()
    except OperationalError as exc:  # no database available in this environment
        pytest.skip(f"no database reachable: {exc}")
    conn.close()

    Base.metadata.create_all(engine)
    session = Session(engine)
    # Clean any leftovers from a previous aborted run.
    session.query(TelemetrySample).filter(TelemetrySample.session_key == _SESSION_KEY).delete()
    session.query(TelemetrySummary).filter(TelemetrySummary.session_key == _SESSION_KEY).delete()
    session.commit()
    try:
        yield session
    finally:
        session.query(TelemetrySample).filter(TelemetrySample.session_key == _SESSION_KEY).delete()
        session.query(TelemetrySummary).filter(
            TelemetrySummary.session_key == _SESSION_KEY
        ).delete()
        session.commit()
        session.close()


def _sample(driver: int, ts: int, speed: int, rpm: int, gear: int, throttle: int, brake: int):
    return TelemetrySample(
        session_key=_SESSION_KEY,
        driver_number=driver,
        date=dt.datetime(2024, 3, 2, 15, 0, ts),
        speed=speed,
        rpm=rpm,
        gear=gear,
        throttle=throttle,
        brake=brake,
        drs=0,
    )


def test_aggregate_rolls_samples_into_one_row_per_driver(db_session):
    db_session.add_all(
        [
            _sample(1, 0, 100, 1000, 3, 100, 0),
            _sample(1, 1, 200, 2000, 5, 50, 5),
            _sample(1, 2, 300, 3000, 7, 99, 0),
            _sample(44, 0, 320, 3200, 8, 100, 0),
        ]
    )
    db_session.commit()

    written = aggregate_telemetry(db_session, [_SESSION_KEY])
    db_session.commit()
    assert written == 2  # one summary row per driver

    row = (
        db_session.query(TelemetrySummary)
        .filter(
            TelemetrySummary.session_key == _SESSION_KEY,
            TelemetrySummary.driver_number == 1,
        )
        .one()
    )
    assert row.sample_count == 3
    assert row.max_speed == 300
    assert row.avg_speed == pytest.approx(200.0)
    assert row.max_rpm == 3000
    assert row.max_gear == 7
    assert row.avg_throttle == pytest.approx(83.0, abs=0.01)
    assert row.full_throttle_fraction == pytest.approx(0.6667, abs=1e-3)  # throttle >= 99
    assert row.brake_fraction == pytest.approx(0.3333, abs=1e-3)  # brake > 0


def test_aggregate_is_idempotent(db_session):
    db_session.add_all([_sample(1, 0, 100, 1000, 3, 100, 0)])
    db_session.commit()

    aggregate_telemetry(db_session, [_SESSION_KEY])
    db_session.commit()
    aggregate_telemetry(db_session, [_SESSION_KEY])
    db_session.commit()

    rows = (
        db_session.query(TelemetrySummary)
        .filter(TelemetrySummary.session_key == _SESSION_KEY)
        .all()
    )
    assert len(rows) == 1  # upsert, not duplicate insert
