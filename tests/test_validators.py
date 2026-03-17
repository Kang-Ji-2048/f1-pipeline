"""Tests for Pydantic schema validation models."""
# Basically just make sure that the data after wrangling is of the correct format

from __future__ import annotations

from datetime import date, datetime

import pytest

from src.models.validators import (
    CircuitData,
    ConstructorData,
    DriverData,
    LapTimeData,
    PitStopData,
    RaceData,
    RaceResultData,
    SessionData,
    TelemetryData,
)


class TestDriverData:
    def test_valid_driver(self):
        raw = {
            "driverId": "max_verstappen",
            "permanentNumber": "33",
            "code": "VER",
            "givenName": "Max",
            "familyName": "Verstappen",
            "dateOfBirth": "1997-09-30",
            "nationality": "Dutch",
        }
        d = DriverData.model_validate(raw)
        assert d.driver_ref == "max_verstappen"
        assert d.number == 33
        assert d.forename == "Max"
        assert d.surname == "Verstappen"
        assert d.date_of_birth == date(1997, 9, 30)

    def test_missing_optional_fields(self):
        raw = {"driverId": "test_driver", "givenName": "Test", "familyName": "Driver"}
        d = DriverData.model_validate(raw)
        assert d.number is None
        assert d.code is None
        assert d.date_of_birth is None

    def test_empty_number_coerced_to_none(self):
        raw = {
            "driverId": "test",
            "permanentNumber": "",
            "givenName": "A",
            "familyName": "B",
        }
        d = DriverData.model_validate(raw)
        assert d.number is None


class TestConstructorData:
    def test_valid_constructor(self):
        raw = {
            "constructorId": "red_bull",
            "name": "Red Bull",
            "nationality": "Austrian",
        }
        c = ConstructorData.model_validate(raw)
        assert c.constructor_ref == "red_bull"
        assert c.name == "Red Bull"


class TestCircuitData:
    def test_valid_circuit_with_coords(self):
        raw = {
            "circuitId": "bahrain",
            "circuitName": "Bahrain International Circuit",
            "lat": "26.0325",
            "long": "50.5106",
            "location": "Sakhir",
            "country": "Bahrain",
        }
        c = CircuitData.model_validate(raw)
        assert c.circuit_ref == "bahrain"
        assert c.latitude == pytest.approx(26.0325)
        assert c.longitude == pytest.approx(50.5106)

    def test_empty_coords(self):
        raw = {
            "circuitId": "test",
            "circuitName": "Test Circuit",
            "lat": "",
            "long": "",
        }
        c = CircuitData.model_validate(raw)
        assert c.latitude is None
        assert c.longitude is None


class TestRaceData:
    def test_valid_race(self):
        raw = {
            "season": "2023",
            "round": "1",
            "raceName": "Bahrain Grand Prix",
            "Circuit": {
                "circuitId": "bahrain",
                "circuitName": "Bahrain International Circuit",
            },
            "date": "2023-03-05",
        }
        r = RaceData.model_validate(raw)
        assert r.season == 2023
        assert r.round == 1
        assert r.race_name == "Bahrain Grand Prix"
        assert r.circuit.circuit_ref == "bahrain"


class TestRaceResultData:
    def test_valid_result(self):
        raw = {
            "number": "1",
            "position": "1",
            "positionText": "1",
            "points": "25",
            "grid": "1",
            "laps": "57",
            "status": "Finished",
            "Driver": {"driverId": "max_verstappen", "givenName": "Max", "familyName": "Verstappen"},
            "Constructor": {"constructorId": "red_bull", "name": "Red Bull"},
        }
        r = RaceResultData.model_validate(raw)
        assert r.position == 1
        assert r.points == 25.0
        assert r.driver.driver_ref == "max_verstappen"

    def test_retired_result(self):
        raw = {
            "number": "44",
            "position": "",
            "positionText": "R",
            "points": "0",
            "grid": "5",
            "laps": "20",
            "status": "Engine",
            "Driver": {"driverId": "hamilton", "givenName": "Lewis", "familyName": "Hamilton"},
            "Constructor": {"constructorId": "mercedes", "name": "Mercedes"},
        }
        r = RaceResultData.model_validate(raw)
        assert r.position is None
        assert r.position_text == "R"
        assert r.status == "Engine"


class TestLapTimeData:
    def test_valid_lap(self):
        raw = {"driverId": "max_verstappen", "lap": "15", "position": "1", "time": "1:32.456"}
        lt = LapTimeData.model_validate(raw)
        assert lt.driver_ref == "max_verstappen"
        assert lt.lap == 15
        assert lt.time_str == "1:32.456"


class TestPitStopData:
    def test_valid_pit_stop(self):
        raw = {
            "driverId": "hamilton",
            "stop": "1",
            "lap": "22",
            "time": "14:45:30",
            "duration": "23.456",
        }
        ps = PitStopData.model_validate(raw)
        assert ps.driver_ref == "hamilton"
        assert ps.stop == 1
        assert ps.lap == 22


class TestSessionData:
    def test_valid_session(self):
        s = SessionData(
            session_key=9001,
            session_name="Race",
            session_type="Race",
            meeting_key=1200,
            location="Bahrain",
            country_name="Bahrain",
            date_start=datetime(2023, 3, 5, 15, 0),
            date_end=datetime(2023, 3, 5, 17, 0),
            year=2023,
        )
        assert s.session_key == 9001
        assert s.year == 2023


class TestTelemetryData:
    def test_valid_telemetry(self):
        t = TelemetryData(
            session_key=9001,
            driver_number=1,
            date=datetime(2023, 3, 5, 15, 1, 0),
            speed=315,
            rpm=12500,
            gear=8,
            throttle=100,
            brake=0,
            drs=1,
        )
        assert t.speed == 315
        assert t.drs == 1

    def test_partial_telemetry(self):
        t = TelemetryData(
            session_key=9001,
            driver_number=1,
            date=datetime(2023, 3, 5, 15, 1, 0),
        )
        assert t.speed is None
        assert t.brake is None
