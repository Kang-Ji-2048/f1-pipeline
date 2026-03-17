"""Shared test fixtures."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture()
def mock_session():
    """Return a mock SQLAlchemy session."""
    session = MagicMock()
    session.execute = MagicMock()
    session.flush = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.close = MagicMock()
    return session


# ── Sample API response fixtures ──────────────────────────────────────────────


@pytest.fixture()
def ergast_driver_response():
    return {
        "MRData": {
            "DriverTable": {
                "Drivers": [
                    {
                        "driverId": "max_verstappen",
                        "permanentNumber": "33",
                        "code": "VER",
                        "givenName": "Max",
                        "familyName": "Verstappen",
                        "dateOfBirth": "1997-09-30",
                        "nationality": "Dutch",
                        "url": "http://en.wikipedia.org/wiki/Max_Verstappen",
                    },
                    {
                        "driverId": "hamilton",
                        "permanentNumber": "44",
                        "code": "HAM",
                        "givenName": "Lewis",
                        "familyName": "Hamilton",
                        "dateOfBirth": "1985-01-07",
                        "nationality": "British",
                        "url": "http://en.wikipedia.org/wiki/Lewis_Hamilton",
                    },
                ],
                "total": "2",
            }
        }
    }


@pytest.fixture()
def ergast_race_response():
    return {
        "MRData": {
            "RaceTable": {
                "Races": [
                    {
                        "season": "2023",
                        "round": "1",
                        "raceName": "Bahrain Grand Prix",
                        "Circuit": {
                            "circuitId": "bahrain",
                            "circuitName": "Bahrain International Circuit",
                            "Location": {
                                "lat": "26.0325",
                                "long": "50.5106",
                                "locality": "Sakhir",
                                "country": "Bahrain",
                            },
                        },
                        "date": "2023-03-05",
                        "time": "15:00:00Z",
                        "url": "http://en.wikipedia.org/wiki/2023_Bahrain_Grand_Prix",
                    }
                ],
                "total": "1",
            }
        }
    }


@pytest.fixture()
def openf1_session_response():
    return [
        {
            "session_key": 9001,
            "session_name": "Race",
            "session_type": "Race",
            "meeting_key": 1200,
            "location": "Bahrain",
            "country_name": "Bahrain",
            "date_start": "2023-03-05T15:00:00",
            "date_end": "2023-03-05T17:00:00",
        }
    ]


@pytest.fixture()
def openf1_car_data_response():
    return [
        {
            "session_key": 9001,
            "driver_number": 1,
            "date": "2023-03-05T15:01:00",
            "speed": 315,
            "rpm": 12500,
            "gear": 8,
            "throttle": 100,
            "brake": 0,
            "drs": 1,
        },
        {
            "session_key": 9001,
            "driver_number": 1,
            "date": "2023-03-05T15:01:01",
            "speed": 310,
            "rpm": 12400,
            "gear": 8,
            "throttle": 95,
            "brake": 5,
            "drs": 0,
        },
    ]
