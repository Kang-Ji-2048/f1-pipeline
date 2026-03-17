"""Ergast API client for historical F1 data."""

from __future__ import annotations

import structlog

from src.api.base import APIClient
from src.config import settings
from src.models.validators import (
    CircuitData,
    ConstructorData,
    DriverData,
    LapTimeData,
    PitStopData,
    RaceData,
    RaceResultData,
)

logger = structlog.get_logger(__name__)


class ErgastClient:
    """Fetches race data from the Ergast F1 API."""

    def __init__(self) -> None:
        self._client = APIClient(settings.ERGAST_BASE_URL)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ErgastClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _paginate(self, path: str, table_key: str, inner_key: str) -> list[dict]:
        """Fetch all pages from an Ergast endpoint."""
        all_items: list[dict] = []
        limit = 100
        offset = 0
        while True:
            data = self._client.get(f"{path}.json", params={"limit": limit, "offset": offset})
            table = data["MRData"][table_key]
            items = table[inner_key]
            all_items.extend(items)
            total = int(table.get("total", len(items)))
            offset += limit
            if offset >= total:
                break
        logger.info("ergast_paginated", path=path, total=len(all_items))
        return all_items

    # ── Dimension data ────────────────────────────────────────────────────

    def get_drivers(self, season: int) -> list[DriverData]:
        raw = self._paginate(f"/{season}/drivers", "DriverTable", "Drivers")
        return [DriverData.model_validate(d) for d in raw]

    def get_constructors(self, season: int) -> list[ConstructorData]:
        raw = self._paginate(f"/{season}/constructors", "ConstructorTable", "Constructors")
        return [ConstructorData.model_validate(c) for c in raw]

    def get_circuits(self, season: int) -> list[CircuitData]:
        raw = self._paginate(f"/{season}/circuits", "CircuitTable", "Circuits")
        return [CircuitData.model_validate(c) for c in _flatten_circuits(raw)]

    # ── Race data ─────────────────────────────────────────────────────────

    def get_races(self, season: int) -> list[RaceData]:
        raw = self._paginate(f"/{season}", "RaceTable", "Races")
        return [RaceData.model_validate(r) for r in raw]

    def get_results(self, season: int, round_num: int) -> list[RaceResultData]:
        raw = self._paginate(
            f"/{season}/{round_num}/results", "RaceTable", "Races"
        )
        if not raw:
            return []
        results_raw = raw[0].get("Results", [])
        parsed: list[RaceResultData] = []
        for r in results_raw:
            # Flatten nested time/fastest-lap fields
            if "Time" in r and isinstance(r["Time"], dict):
                r["time_millis"] = r["Time"].get("millis")
            if "FastestLap" in r and isinstance(r["FastestLap"], dict):
                fl = r["FastestLap"]
                r["fastest_lap_rank"] = fl.get("rank")
                if "Time" in fl:
                    r["fastest_lap_time"] = fl["Time"].get("time")
                if "AverageSpeed" in fl:
                    r["fastest_lap_speed"] = fl["AverageSpeed"].get("speed")
            parsed.append(RaceResultData.model_validate(r))
        return parsed

    def get_lap_times(self, season: int, round_num: int) -> list[LapTimeData]:
        raw = self._paginate(
            f"/{season}/{round_num}/laps", "RaceTable", "Races"
        )
        if not raw:
            return []
        laps: list[LapTimeData] = []
        for race_data in raw:
            for lap_entry in race_data.get("Laps", []):
                lap_num = lap_entry["number"]
                for timing in lap_entry.get("Timings", []):
                    timing["lap"] = lap_num
                    laps.append(LapTimeData.model_validate(timing))
        return laps

    def get_pit_stops(self, season: int, round_num: int) -> list[PitStopData]:
        raw = self._paginate(
            f"/{season}/{round_num}/pitstops", "RaceTable", "Races"
        )
        if not raw:
            return []
        stops: list[PitStopData] = []
        for race_data in raw:
            for ps in race_data.get("PitStops", []):
                stops.append(PitStopData.model_validate(ps))
        return stops


def _flatten_circuits(raw: list[dict]) -> list[dict]:
    """Flatten nested Location dict into the circuit record."""
    flattened = []
    for c in raw:
        loc = c.pop("Location", {})
        c["lat"] = loc.get("lat")
        c["long"] = loc.get("long")
        c["location"] = loc.get("locality")
        c["country"] = loc.get("country")
        flattened.append(c)
    return flattened
