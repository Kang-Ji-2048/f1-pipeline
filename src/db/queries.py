"""Database query interface for F1 data."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.db.engine import get_session
from src.db.schema import (
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


def _parse_lap_time(time_str: str | None) -> int | None:
    """Convert an Ergast lap-time string to milliseconds.

    Accepts ``"M:SS.mmm"`` (e.g. ``"1:32.500"``) or plain seconds
    ``"SS.mmm"``. Returns ``None`` when the value cannot be parsed.
    """
    if not time_str:
        return None
    try:
        minutes = 0
        rest = time_str
        if ":" in time_str:
            mins, rest = time_str.split(":", 1)
            minutes = int(mins)
        seconds = float(rest)
        return int(round((minutes * 60 + seconds) * 1000))
    except (ValueError, TypeError):
        return None


class F1Database:
    """High-level read interface for querying ingested F1 data."""

    def __init__(self, session: Session | None = None) -> None:
        self._external_session = session

    def _get_session(self) -> Session:
        if self._external_session is not None:
            return self._external_session
        raise RuntimeError(
            "No session provided. Use F1Database as a context manager or pass a session."
        )

    def __enter__(self) -> F1Database:
        if self._external_session is None:
            self._ctx = get_session()
            self._external_session = self._ctx.__enter__()
        return self

    def __exit__(self, *exc: Any) -> None:
        if hasattr(self, "_ctx"):
            self._ctx.__exit__(*exc)
            self._external_session = None

    # ── Seasons ──────────────────────────────────────────────────────────────

    def get_seasons(self) -> list[int]:
        """Return all ingested season years, sorted."""
        session = self._get_session()
        rows = session.query(Season.year).order_by(Season.year).all()
        return [r.year for r in rows]

    # ── Drivers ──────────────────────────────────────────────────────────────

    def get_drivers(self, season_year: int) -> list[dict[str, Any]]:
        """Return drivers who participated in a given season."""
        session = self._get_session()
        subq = (
            session.query(RaceResult.driver_ref)
            .join(Race, RaceResult.race_id == Race.id)
            .filter(Race.season_year == season_year)
            .distinct()
            .subquery()
        )
        drivers = (
            session.query(Driver)
            .filter(Driver.driver_ref.in_(session.query(subq.c.driver_ref)))
            .order_by(Driver.surname)
            .all()
        )
        return [
            {
                "driver_ref": d.driver_ref,
                "code": d.code,
                "forename": d.forename,
                "surname": d.surname,
                "nationality": d.nationality,
                "number": d.number,
            }
            for d in drivers
        ]

    # ── Constructors ─────────────────────────────────────────────────────────

    def get_constructors(self, season_year: int) -> list[dict[str, Any]]:
        """Return constructors who participated in a given season."""
        session = self._get_session()
        subq = (
            session.query(RaceResult.constructor_ref)
            .join(Race, RaceResult.race_id == Race.id)
            .filter(Race.season_year == season_year)
            .distinct()
            .subquery()
        )
        constructors = (
            session.query(Constructor)
            .filter(Constructor.constructor_ref.in_(session.query(subq.c.constructor_ref)))
            .order_by(Constructor.name)
            .all()
        )
        return [
            {
                "constructor_ref": c.constructor_ref,
                "name": c.name,
                "nationality": c.nationality,
            }
            for c in constructors
        ]

    # ── Races ────────────────────────────────────────────────────────────────

    def get_races(self, season_year: int) -> list[dict[str, Any]]:
        """Return all races for a season, ordered by round."""
        session = self._get_session()
        races = (
            session.query(Race).filter(Race.season_year == season_year).order_by(Race.round).all()
        )
        return [
            {
                "id": r.id,
                "round": r.round,
                "name": r.name,
                "circuit_ref": r.circuit_ref,
                "date": str(r.date),
            }
            for r in races
        ]

    # ── Race results ─────────────────────────────────────────────────────────

    def get_race_results(self, season_year: int, round_num: int) -> list[dict[str, Any]]:
        """Return finishing order for a specific race."""
        session = self._get_session()
        race = (
            session.query(Race)
            .filter(Race.season_year == season_year, Race.round == round_num)
            .first()
        )
        if race is None:
            return []

        results = (
            session.query(RaceResult)
            .filter(RaceResult.race_id == race.id)
            .order_by(RaceResult.position.nulls_last())
            .all()
        )
        return [
            {
                "position": r.position,
                "position_text": r.position_text,
                "driver_ref": r.driver_ref,
                "constructor_ref": r.constructor_ref,
                "grid": r.grid,
                "points": r.points,
                "laps": r.laps,
                "status": r.status,
                "time_millis": r.time_millis,
                "fastest_lap_time": r.fastest_lap_time,
            }
            for r in results
        ]

    # ── Standings ─────────────────────────────────────────────────────────────

    def get_driver_standings(self, season_year: int) -> list[dict[str, Any]]:
        """Return cumulative driver points for a season, descending."""
        session = self._get_session()
        rows = (
            session.query(
                RaceResult.driver_ref,
                func.sum(RaceResult.points).label("total_points"),
                func.count(RaceResult.id).label("races"),
            )
            .join(Race, RaceResult.race_id == Race.id)
            .filter(Race.season_year == season_year)
            .group_by(RaceResult.driver_ref)
            .order_by(func.sum(RaceResult.points).desc())
            .all()
        )
        return [
            {
                "driver_ref": r.driver_ref,
                "total_points": float(r.total_points),
                "races": r.races,
            }
            for r in rows
        ]

    def get_constructor_standings(self, season_year: int) -> list[dict[str, Any]]:
        """Return cumulative constructor points for a season, descending."""
        session = self._get_session()
        rows = (
            session.query(
                RaceResult.constructor_ref,
                func.sum(RaceResult.points).label("total_points"),
                func.count(RaceResult.id).label("results"),
            )
            .join(Race, RaceResult.race_id == Race.id)
            .filter(Race.season_year == season_year)
            .group_by(RaceResult.constructor_ref)
            .order_by(func.sum(RaceResult.points).desc())
            .all()
        )
        return [
            {
                "constructor_ref": r.constructor_ref,
                "total_points": float(r.total_points),
                "results": r.results,
            }
            for r in rows
        ]

    def get_results_frame(self) -> list[dict[str, Any]]:
        """Return one row per (race, driver) for model training/prediction.

        Ordered by date then round so downstream feature engineering can compute
        leakage-safe rolling stats. Includes the grid (qualifying) position, which
        is known before the race, plus the finishing position and points target.
        """
        session = self._get_session()
        rows = (
            session.query(
                Race.season_year,
                Race.round,
                Race.date,
                Race.circuit_ref,
                RaceResult.driver_ref,
                RaceResult.constructor_ref,
                RaceResult.grid,
                RaceResult.position,
                RaceResult.points,
            )
            .join(RaceResult, RaceResult.race_id == Race.id)
            .order_by(Race.date, Race.round)
            .all()
        )
        return [
            {
                "season": r.season_year,
                "round": r.round,
                "date": str(r.date),
                "circuit_ref": r.circuit_ref,
                "driver_ref": r.driver_ref,
                "constructor_ref": r.constructor_ref,
                "grid": r.grid,
                "position": r.position,
                "points": float(r.points or 0.0),
            }
            for r in rows
        ]

    def get_circuits(self) -> list[dict[str, Any]]:
        """Return all circuits, sorted by name."""
        session = self._get_session()
        rows = session.query(Circuit).order_by(Circuit.name).all()
        return [{"circuit_ref": c.circuit_ref, "name": c.name} for c in rows]

    def get_circuit_winners(self, circuit_ref: str) -> list[dict[str, Any]]:
        """Return race winners (P1 finishers) at a circuit across all seasons.

        Ordered by win count, descending. The total across drivers equals the
        number of races held at the circuit.
        """
        session = self._get_session()
        rows = (
            session.query(RaceResult.driver_ref, func.count().label("wins"))
            .join(Race, RaceResult.race_id == Race.id)
            .filter(Race.circuit_ref == circuit_ref, RaceResult.position == 1)
            .group_by(RaceResult.driver_ref)
            .order_by(func.count().desc(), RaceResult.driver_ref)
            .all()
        )
        return [{"driver_ref": r.driver_ref, "wins": int(r.wins)} for r in rows]

    def get_constructor_results(
        self, season_year: int, constructor_ref: str
    ) -> list[dict[str, Any]]:
        """Return a constructor's points per round for a season (sum of both cars)."""
        session = self._get_session()
        rows = (
            session.query(Race.round, func.sum(RaceResult.points).label("points"))
            .join(RaceResult, RaceResult.race_id == Race.id)
            .filter(
                Race.season_year == season_year,
                RaceResult.constructor_ref == constructor_ref,
            )
            .group_by(Race.round)
            .order_by(Race.round)
            .all()
        )
        return [{"round": r.round, "points": float(r.points or 0.0)} for r in rows]

    def get_driver_results(self, season_year: int, driver_ref: str) -> list[dict[str, Any]]:
        """Return a driver's per-round results for a season, ordered by round."""
        session = self._get_session()
        rows = (
            session.query(
                Race.round,
                RaceResult.position,
                RaceResult.points,
                RaceResult.status,
            )
            .join(RaceResult, RaceResult.race_id == Race.id)
            .filter(Race.season_year == season_year, RaceResult.driver_ref == driver_ref)
            .order_by(Race.round)
            .all()
        )
        return [
            {
                "round": r.round,
                "position": r.position,
                "points": float(r.points or 0.0),
                "status": r.status,
            }
            for r in rows
        ]

    # ── Lap times ────────────────────────────────────────────────────────────

    def get_lap_times(
        self,
        season_year: int,
        round_num: int,
        driver_ref: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return lap times for a race, optionally filtered to one driver."""
        session = self._get_session()
        race = (
            session.query(Race)
            .filter(Race.season_year == season_year, Race.round == round_num)
            .first()
        )
        if race is None:
            return []

        query = session.query(LapTime).filter(LapTime.race_id == race.id)
        if driver_ref:
            query = query.filter(LapTime.driver_ref == driver_ref)
        laps = query.order_by(LapTime.driver_ref, LapTime.lap).all()

        return [
            {
                "driver_ref": lt.driver_ref,
                "lap": lt.lap,
                "position": lt.position,
                "time_str": lt.time_str,
                "time_millis": lt.time_millis,
            }
            for lt in laps
        ]

    # ── Pit stops ────────────────────────────────────────────────────────────

    def get_pit_stops(
        self,
        season_year: int,
        round_num: int,
        driver_ref: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return pit stops for a race, optionally filtered to one driver."""
        session = self._get_session()
        race = (
            session.query(Race)
            .filter(Race.season_year == season_year, Race.round == round_num)
            .first()
        )
        if race is None:
            return []

        query = session.query(PitStop).filter(PitStop.race_id == race.id)
        if driver_ref:
            query = query.filter(PitStop.driver_ref == driver_ref)
        stops = query.order_by(PitStop.driver_ref, PitStop.stop).all()

        return [
            {
                "driver_ref": ps.driver_ref,
                "stop": ps.stop,
                "lap": ps.lap,
                "time_of_day": ps.time_of_day,
                "duration_millis": ps.duration_millis,
            }
            for ps in stops
        ]

    # ── Telemetry ────────────────────────────────────────────────────────────

    def get_sessions(self, year: int) -> list[dict[str, Any]]:
        """Return OpenF1 sessions for a year."""
        session = self._get_session()
        rows = (
            session.query(SessionInfo)
            .filter(SessionInfo.year == year)
            .order_by(SessionInfo.date_start)
            .all()
        )
        return [
            {
                "session_key": s.session_key,
                "session_name": s.session_name,
                "session_type": s.session_type,
                "location": s.location,
                "country_name": s.country_name,
                "date_start": str(s.date_start) if s.date_start else None,
            }
            for s in rows
        ]

    def get_telemetry_drivers(self, session_key: int) -> list[int]:
        """Return the sorted, unique driver numbers with telemetry in a session."""
        session = self._get_session()
        rows = (
            session.query(TelemetrySample.driver_number)
            .filter(TelemetrySample.session_key == session_key)
            .distinct()
            .order_by(TelemetrySample.driver_number)
            .all()
        )
        return [int(r[0]) for r in rows]

    def get_telemetry(
        self,
        session_key: int,
        driver_number: int,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Return telemetry samples for a driver in a session."""
        session = self._get_session()
        rows = (
            session.query(TelemetrySample)
            .filter(
                TelemetrySample.session_key == session_key,
                TelemetrySample.driver_number == driver_number,
            )
            .order_by(TelemetrySample.date)
            .limit(limit)
            .all()
        )
        return [
            {
                "date": str(t.date),
                "speed": t.speed,
                "rpm": t.rpm,
                "gear": t.gear,
                "throttle": t.throttle,
                "brake": t.brake,
                "drs": t.drs,
            }
            for t in rows
        ]

    # ── Dashboard aggregations ─────────────────────────────────────────────────

    def get_lap_time_distribution(self, season_year: int, round_num: int) -> list[dict[str, Any]]:
        """Return per-lap times in milliseconds for a race.

        Uses stored ``time_millis`` where present, otherwise parses ``time_str``.
        Laps with no resolvable time are omitted.
        """
        session = self._get_session()
        race = (
            session.query(Race)
            .filter(Race.season_year == season_year, Race.round == round_num)
            .first()
        )
        if race is None:
            return []

        laps = (
            session.query(LapTime)
            .filter(LapTime.race_id == race.id)
            .order_by(LapTime.driver_ref, LapTime.lap)
            .all()
        )
        rows: list[dict[str, Any]] = []
        for lt in laps:
            millis = lt.time_millis if lt.time_millis is not None else _parse_lap_time(lt.time_str)
            if millis is None:
                continue
            rows.append({"driver_ref": lt.driver_ref, "lap": lt.lap, "time_millis": millis})
        return rows

    def get_stints(self, season_year: int, round_num: int) -> list[dict[str, Any]]:
        """Return per-driver stints derived from pit-stop laps.

        A stint runs from the lap after the previous pit stop (or lap 1) up to
        and including the next pit-stop lap, with the final stint ending on the
        driver's last completed lap.
        """
        session = self._get_session()
        race = (
            session.query(Race)
            .filter(Race.season_year == season_year, Race.round == round_num)
            .first()
        )
        if race is None:
            return []

        last_lap: dict[str, int] = {}
        for driver_ref, max_lap in (
            session.query(LapTime.driver_ref, func.max(LapTime.lap))
            .filter(LapTime.race_id == race.id)
            .group_by(LapTime.driver_ref)
            .all()
        ):
            last_lap[str(driver_ref)] = int(max_lap)

        pit_laps: dict[str, list[int]] = {}
        for ps in (
            session.query(PitStop)
            .filter(PitStop.race_id == race.id)
            .order_by(PitStop.driver_ref, PitStop.stop)
            .all()
        ):
            pit_laps.setdefault(str(ps.driver_ref), []).append(int(ps.lap))

        stints: list[dict[str, Any]] = []
        for driver_ref in sorted(last_lap):
            final_lap = last_lap[driver_ref]
            boundaries = [lap for lap in sorted(pit_laps.get(driver_ref, [])) if lap < final_lap]
            boundaries.append(final_lap)
            start = 1
            for stint_num, end in enumerate(boundaries, 1):
                stints.append(
                    {
                        "driver_ref": driver_ref,
                        "stint": stint_num,
                        "start_lap": start,
                        "end_lap": end,
                        "laps": end - start + 1,
                    }
                )
                start = end + 1
        return stints
