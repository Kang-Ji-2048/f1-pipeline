"""Pydantic models for schema validation of incoming API data."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator


# ── Ergast API models ─────────────────────────────────────────────────────────


class DriverData(BaseModel):
    driver_ref: str = Field(alias="driverId")
    number: int | None = Field(default=None, alias="permanentNumber")
    code: str | None = None
    forename: str = Field(alias="givenName")
    surname: str = Field(alias="familyName")
    date_of_birth: date | None = Field(default=None, alias="dateOfBirth")
    nationality: str | None = None
    url: str | None = None

    model_config = {"populate_by_name": True}

    @field_validator("number", mode="before")
    @classmethod
    def coerce_number(cls, v: str | int | None) -> int | None:
        if v is None or v == "":
            return None
        return int(v)


class ConstructorData(BaseModel):
    constructor_ref: str = Field(alias="constructorId")
    name: str
    nationality: str | None = None
    url: str | None = None

    model_config = {"populate_by_name": True}


class CircuitData(BaseModel):
    circuit_ref: str = Field(alias="circuitId")
    name: str = Field(alias="circuitName")
    location: str | None = None
    country: str | None = None
    latitude: float | None = Field(default=None, alias="lat")
    longitude: float | None = Field(default=None, alias="long")
    url: str | None = None

    model_config = {"populate_by_name": True}

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def coerce_coord(cls, v: str | float | None) -> float | None:
        if v is None or v == "":
            return None
        return float(v)


class RaceData(BaseModel):
    season: int
    round: int
    race_name: str = Field(alias="raceName")
    circuit: CircuitData = Field(alias="Circuit")
    date: date
    time: str | None = None
    url: str | None = None

    model_config = {"populate_by_name": True}

    @field_validator("season", "round", mode="before")
    @classmethod
    def coerce_int(cls, v: str | int) -> int:
        return int(v)


class RaceResultData(BaseModel):
    number: int | None = None
    position: int | None = None
    position_text: str | None = Field(default=None, alias="positionText")
    points: float = 0
    grid: int | None = None
    laps: int | None = None
    status: str | None = None
    driver: DriverData = Field(alias="Driver")
    constructor: ConstructorData = Field(alias="Constructor")
    time_millis: int | None = None
    fastest_lap_rank: int | None = None
    fastest_lap_time: str | None = None
    fastest_lap_speed: float | None = None

    model_config = {"populate_by_name": True}

    @field_validator("number", "position", "grid", "laps", "fastest_lap_rank", mode="before")
    @classmethod
    def coerce_optional_int(cls, v: str | int | None) -> int | None:
        if v is None or v == "":
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    @field_validator("points", "fastest_lap_speed", mode="before")
    @classmethod
    def coerce_float(cls, v: str | float | None) -> float:
        if v is None or v == "":
            return 0.0
        try:
            return float(v)
        except (ValueError, TypeError):
            return 0.0


class LapTimeData(BaseModel):
    driver_ref: str = Field(alias="driverId")
    lap: int
    position: int | None = None
    time_str: str | None = Field(default=None, alias="time")

    model_config = {"populate_by_name": True}

    @field_validator("lap", mode="before")
    @classmethod
    def coerce_lap(cls, v: str | int) -> int:
        return int(v)

    @field_validator("position", mode="before")
    @classmethod
    def coerce_pos(cls, v: str | int | None) -> int | None:
        if v is None or v == "":
            return None
        return int(v)


class PitStopData(BaseModel):
    driver_ref: str = Field(alias="driverId")
    stop: int
    lap: int
    time_of_day: str | None = Field(default=None, alias="time")
    duration: str | None = None

    model_config = {"populate_by_name": True}

    @field_validator("stop", "lap", mode="before")
    @classmethod
    def coerce_int(cls, v: str | int) -> int:
        return int(v)


# ── OpenF1 API models ────────────────────────────────────────────────────────


class SessionData(BaseModel):
    session_key: int
    session_name: str | None = None
    session_type: str | None = None
    meeting_key: int | None = None
    location: str | None = None
    country_name: str | None = None
    date_start: datetime | None = None
    date_end: datetime | None = None
    year: int


class TelemetryData(BaseModel):
    session_key: int
    driver_number: int
    date: datetime
    speed: int | None = None
    rpm: int | None = None
    gear: int | None = None
    throttle: int | None = None
    brake: int | None = None
    drs: int | None = None
