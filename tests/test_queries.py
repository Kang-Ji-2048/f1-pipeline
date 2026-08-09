"""Tests for dashboard-oriented query helpers on F1Database."""

from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.db.queries import F1Database
from src.db.schema import Base, Circuit, LapTime, PitStop, Race, RaceResult, TelemetrySample


@pytest.fixture()
def seeded_session():
    """In-memory SQLite session seeded with one race, two drivers, laps and pits."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)

    session.add(
        Race(
            id=1,
            season_year=2023,
            round=1,
            name="Test Grand Prix",
            circuit_ref="testcircuit",
            date=date(2023, 3, 5),
        )
    )
    # SQLite does not autoincrement BigInteger PKs, so ids are assigned explicitly.
    lap_id = 1
    # ver: 5 laps, pits after lap 2 -> stints 1-2 and 3-5
    for lap, t in enumerate(["1:32.500", "1:31.000", "1:33.200", "1:30.900", "1:31.400"], 1):
        session.add(LapTime(id=lap_id, race_id=1, driver_ref="ver", lap=lap, time_str=t))
        lap_id += 1
    session.add(PitStop(id=1, race_id=1, driver_ref="ver", stop=1, lap=2))
    # ham: 5 laps, no pit -> single stint 1-5; one lap already has time_millis
    for lap in range(1, 6):
        session.add(
            LapTime(
                id=lap_id,
                race_id=1,
                driver_ref="ham",
                lap=lap,
                time_str=None if lap == 1 else "1:32.000",
                time_millis=91000 if lap == 1 else None,
            )
        )
        lap_id += 1

    session.commit()
    yield session
    session.close()


class TestLapTimeDistribution:
    def test_returns_millis_for_all_laps(self, seeded_session):
        db = F1Database(session=seeded_session)
        rows = db.get_lap_time_distribution(2023, 1)

        # 10 laps total, all with a resolvable millis value
        assert len(rows) == 10
        assert all(r["time_millis"] is not None for r in rows)

        ver_lap1 = next(r for r in rows if r["driver_ref"] == "ver" and r["lap"] == 1)
        assert ver_lap1["time_millis"] == 92500  # "1:32.500" parsed

        ham_lap1 = next(r for r in rows if r["driver_ref"] == "ham" and r["lap"] == 1)
        assert ham_lap1["time_millis"] == 91000  # pre-existing time_millis kept

    def test_empty_for_unknown_race(self, seeded_session):
        db = F1Database(session=seeded_session)
        assert db.get_lap_time_distribution(2023, 99) == []


class TestStints:
    def test_derives_stints_from_pit_stops(self, seeded_session):
        db = F1Database(session=seeded_session)
        stints = db.get_stints(2023, 1)

        ver = [s for s in stints if s["driver_ref"] == "ver"]
        assert ver == [
            {"driver_ref": "ver", "stint": 1, "start_lap": 1, "end_lap": 2, "laps": 2},
            {"driver_ref": "ver", "stint": 2, "start_lap": 3, "end_lap": 5, "laps": 3},
        ]

        ham = [s for s in stints if s["driver_ref"] == "ham"]
        assert ham == [
            {"driver_ref": "ham", "stint": 1, "start_lap": 1, "end_lap": 5, "laps": 5},
        ]

    def test_empty_for_unknown_race(self, seeded_session):
        db = F1Database(session=seeded_session)
        assert db.get_stints(2023, 99) == []


class TestTelemetryDrivers:
    def test_returns_sorted_unique_driver_numbers(self):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        session = Session(engine)
        session.add_all(
            [
                TelemetrySample(
                    id=1, session_key=9001, driver_number=44, date=datetime(2023, 3, 5, 15, 0, 0)
                ),
                TelemetrySample(
                    id=2, session_key=9001, driver_number=1, date=datetime(2023, 3, 5, 15, 0, 1)
                ),
                TelemetrySample(
                    id=3, session_key=9001, driver_number=44, date=datetime(2023, 3, 5, 15, 0, 2)
                ),
                TelemetrySample(
                    id=4, session_key=9002, driver_number=16, date=datetime(2023, 3, 5, 16, 0, 0)
                ),
            ]
        )
        session.commit()

        db = F1Database(session=session)
        assert db.get_telemetry_drivers(9001) == [1, 44]
        assert db.get_telemetry_drivers(9999) == []
        session.close()


class TestDriverResults:
    def test_returns_per_round_results_ordered(self):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        session = Session(engine)
        session.add_all(
            [
                Race(
                    id=1,
                    season_year=2023,
                    round=1,
                    name="R1",
                    circuit_ref="c",
                    date=date(2023, 3, 5),
                ),
                Race(
                    id=2,
                    season_year=2023,
                    round=2,
                    name="R2",
                    circuit_ref="c",
                    date=date(2023, 3, 12),
                ),
                RaceResult(
                    id=1,
                    race_id=2,
                    driver_ref="ver",
                    constructor_ref="rb",
                    position=3,
                    points=15.0,
                    status="Finished",
                ),
                RaceResult(
                    id=2,
                    race_id=1,
                    driver_ref="ver",
                    constructor_ref="rb",
                    position=1,
                    points=25.0,
                    status="Finished",
                ),
                RaceResult(
                    id=3,
                    race_id=1,
                    driver_ref="ham",
                    constructor_ref="mer",
                    position=2,
                    points=18.0,
                    status="Finished",
                ),
            ]
        )
        session.commit()

        db = F1Database(session=session)
        assert db.get_driver_results(2023, "ver") == [
            {"round": 1, "position": 1, "points": 25.0, "status": "Finished"},
            {"round": 2, "position": 3, "points": 15.0, "status": "Finished"},
        ]
        assert db.get_driver_results(2023, "nobody") == []
        session.close()


class TestConstructorResults:
    def test_sums_points_per_round(self):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        session = Session(engine)
        session.add_all(
            [
                Race(
                    id=1,
                    season_year=2023,
                    round=1,
                    name="R1",
                    circuit_ref="c",
                    date=date(2023, 3, 5),
                ),
                Race(
                    id=2,
                    season_year=2023,
                    round=2,
                    name="R2",
                    circuit_ref="c",
                    date=date(2023, 3, 12),
                ),
                RaceResult(
                    id=1,
                    race_id=1,
                    driver_ref="nor",
                    constructor_ref="mclaren",
                    position=1,
                    points=25.0,
                    status="F",
                ),
                RaceResult(
                    id=2,
                    race_id=1,
                    driver_ref="pia",
                    constructor_ref="mclaren",
                    position=3,
                    points=15.0,
                    status="F",
                ),
                RaceResult(
                    id=3,
                    race_id=2,
                    driver_ref="nor",
                    constructor_ref="mclaren",
                    position=2,
                    points=18.0,
                    status="F",
                ),
                RaceResult(
                    id=4,
                    race_id=1,
                    driver_ref="ver",
                    constructor_ref="red_bull",
                    position=2,
                    points=18.0,
                    status="F",
                ),
            ]
        )
        session.commit()

        db = F1Database(session=session)
        assert db.get_constructor_results(2023, "mclaren") == [
            {"round": 1, "points": 40.0},
            {"round": 2, "points": 18.0},
        ]
        assert db.get_constructor_results(2023, "nobody") == []
        session.close()


class TestCircuitInsights:
    def _seed(self):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        session = Session(engine)
        session.add_all(
            [
                Circuit(circuit_ref="monza", name="Monza"),
                Circuit(circuit_ref="spa", name="Spa"),
                Race(
                    id=1,
                    season_year=2022,
                    round=1,
                    name="Italian GP",
                    circuit_ref="monza",
                    date=date(2022, 9, 1),
                ),
                Race(
                    id=2,
                    season_year=2023,
                    round=1,
                    name="Italian GP",
                    circuit_ref="monza",
                    date=date(2023, 9, 1),
                ),
                Race(
                    id=3,
                    season_year=2023,
                    round=2,
                    name="Belgian GP",
                    circuit_ref="spa",
                    date=date(2023, 8, 1),
                ),
                RaceResult(
                    id=1,
                    race_id=1,
                    driver_ref="ver",
                    constructor_ref="rb",
                    position=1,
                    points=25.0,
                    status="F",
                ),
                RaceResult(
                    id=2,
                    race_id=2,
                    driver_ref="ver",
                    constructor_ref="rb",
                    position=1,
                    points=25.0,
                    status="F",
                ),
                RaceResult(
                    id=3,
                    race_id=2,
                    driver_ref="lec",
                    constructor_ref="fer",
                    position=2,
                    points=18.0,
                    status="F",
                ),
                RaceResult(
                    id=4,
                    race_id=3,
                    driver_ref="lec",
                    constructor_ref="fer",
                    position=1,
                    points=25.0,
                    status="F",
                ),
            ]
        )
        session.commit()
        return session

    def test_get_circuits_sorted(self):
        session = self._seed()
        db = F1Database(session=session)
        assert db.get_circuits() == [
            {"circuit_ref": "monza", "name": "Monza"},
            {"circuit_ref": "spa", "name": "Spa"},
        ]
        session.close()

    def test_circuit_winners_count_p1_across_seasons(self):
        session = self._seed()
        db = F1Database(session=session)
        assert db.get_circuit_winners("monza") == [{"driver_ref": "ver", "wins": 2}]
        assert db.get_circuit_winners("spa") == [{"driver_ref": "lec", "wins": 1}]
        assert db.get_circuit_winners("none") == []
        session.close()


class TestResultsFrame:
    def test_returns_training_rows_ordered_by_date(self):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        session = Session(engine)
        session.add_all(
            [
                Race(
                    id=1,
                    season_year=2023,
                    round=2,
                    name="R2",
                    circuit_ref="spa",
                    date=date(2023, 4, 1),
                ),
                Race(
                    id=2,
                    season_year=2023,
                    round=1,
                    name="R1",
                    circuit_ref="monza",
                    date=date(2023, 3, 1),
                ),
                RaceResult(
                    id=1,
                    race_id=1,
                    driver_ref="ver",
                    constructor_ref="rb",
                    grid=1,
                    position=1,
                    points=25.0,
                    status="F",
                ),
                RaceResult(
                    id=2,
                    race_id=2,
                    driver_ref="ver",
                    constructor_ref="rb",
                    grid=2,
                    position=2,
                    points=18.0,
                    status="F",
                ),
            ]
        )
        session.commit()

        db = F1Database(session=session)
        frame = db.get_results_frame()
        # ordered by date: monza (Mar) before spa (Apr)
        assert [r["circuit_ref"] for r in frame] == ["monza", "spa"]
        assert frame[0]["grid"] == 2
        assert frame[0]["points"] == 18.0
        assert frame[1]["driver_ref"] == "ver"
        session.close()
