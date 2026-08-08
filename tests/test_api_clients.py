"""Tests for API client layers (mocked HTTP)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.api.base import APIClient
from src.api.ergast import ErgastClient
from src.api.openf1 import OpenF1Client


class TestAPIClientRateLimiting:
    @patch("src.api.base.time")
    def test_throttle_sleeps_between_rapid_requests(self, mock_time):
        # monotonic returns the same instant for both throttle calls, so the
        # second call sees ~0 elapsed and must sleep to honour the interval.
        mock_time.monotonic.return_value = 1000.0
        client = APIClient("https://example.com")

        client._throttle()  # first call: primes last-request timestamp
        client._throttle()  # second call: no time has passed -> must wait

        mock_time.sleep.assert_called_once()
        assert mock_time.sleep.call_args[0][0] == pytest.approx(client._min_interval)

    def test_parse_retry_after_reads_seconds(self):
        resp = MagicMock()
        resp.headers = {"Retry-After": "7"}
        assert APIClient._parse_retry_after(resp) == 7.0

    def test_parse_retry_after_defaults_when_absent(self):
        resp = MagicMock()
        resp.headers = {}
        assert APIClient._parse_retry_after(resp) == 2.0


class TestErgastClient:
    @patch("src.api.ergast.APIClient")
    def test_get_drivers(self, mock_api_cls, ergast_driver_response):
        mock_client = MagicMock()
        mock_api_cls.return_value = mock_client
        mock_client.get.return_value = ergast_driver_response

        with ErgastClient() as client:
            drivers = client.get_drivers(2023)

        assert len(drivers) == 2
        assert drivers[0].driver_ref == "max_verstappen"
        assert drivers[1].driver_ref == "hamilton"

    @patch("src.api.ergast.APIClient")
    def test_get_races(self, mock_api_cls, ergast_race_response):
        mock_client = MagicMock()
        mock_api_cls.return_value = mock_client
        mock_client.get.return_value = ergast_race_response

        with ErgastClient() as client:
            races = client.get_races(2023)

        assert len(races) == 1
        assert races[0].race_name == "Bahrain Grand Prix"
        assert races[0].circuit.circuit_ref == "bahrain"

    @patch("src.api.ergast.APIClient")
    def test_get_results_empty(self, mock_api_cls):
        mock_client = MagicMock()
        mock_api_cls.return_value = mock_client
        mock_client.get.return_value = {"MRData": {"RaceTable": {"Races": [], "total": "0"}}}

        with ErgastClient() as client:
            results = client.get_results(2023, 1)

        assert results == []


class TestOpenF1Client:
    @patch("src.api.openf1.APIClient")
    def test_get_sessions(self, mock_api_cls, openf1_session_response):
        mock_client = MagicMock()
        mock_api_cls.return_value = mock_client
        mock_client.get.return_value = openf1_session_response

        with OpenF1Client() as client:
            sessions = client.get_sessions(2023)

        assert len(sessions) == 1
        assert sessions[0].session_key == 9001
        assert sessions[0].year == 2023

    @patch("src.api.openf1.APIClient")
    def test_get_car_data(self, mock_api_cls, openf1_car_data_response):
        mock_client = MagicMock()
        mock_api_cls.return_value = mock_client
        mock_client.get.return_value = openf1_car_data_response

        with OpenF1Client() as client:
            samples = client.get_car_data(9001, driver_number=1)

        assert len(samples) == 2
        assert samples[0].speed == 315
        assert samples[1].brake == 5

    @patch("src.api.openf1.APIClient")
    def test_get_car_data_no_driver_filter(self, mock_api_cls, openf1_car_data_response):
        mock_client = MagicMock()
        mock_api_cls.return_value = mock_client
        mock_client.get.return_value = openf1_car_data_response

        with OpenF1Client() as client:
            client.get_car_data(9001)

        mock_client.get.assert_called_once_with("/car_data", params={"session_key": 9001})

    @patch("src.api.openf1.APIClient")
    def test_get_latest_car_data_defaults_to_latest(self, mock_api_cls, openf1_car_data_response):
        mock_client = MagicMock()
        mock_api_cls.return_value = mock_client
        mock_client.get.return_value = openf1_car_data_response

        with OpenF1Client() as client:
            samples = client.get_latest_car_data()

        mock_client.get.assert_called_once_with("/car_data", params={"session_key": "latest"})
        assert len(samples) == 2
        assert samples[0].speed == 315

    @patch("src.api.openf1.APIClient")
    def test_get_latest_car_data_with_after_cursor(self, mock_api_cls, openf1_car_data_response):
        mock_client = MagicMock()
        mock_api_cls.return_value = mock_client
        mock_client.get.return_value = openf1_car_data_response

        with OpenF1Client() as client:
            client.get_latest_car_data(9001, after="2023-03-05T15:01:00")

        mock_client.get.assert_called_once_with(
            "/car_data",
            params={"session_key": 9001, "date>": "2023-03-05T15:01:00"},
        )

    @patch("src.api.openf1.APIClient")
    def test_get_session_drivers_returns_sorted_unique_numbers(self, mock_api_cls):
        mock_client = MagicMock()
        mock_api_cls.return_value = mock_client
        mock_client.get.return_value = [
            {"driver_number": 44, "session_key": 9001},
            {"driver_number": 1, "session_key": 9001},
            {"driver_number": 44, "session_key": 9001},
        ]

        with OpenF1Client() as client:
            drivers = client.get_session_drivers(9001)

        mock_client.get.assert_called_once_with("/drivers", params={"session_key": 9001})
        assert drivers == [1, 44]
