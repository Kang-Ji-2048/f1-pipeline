"""Tests for the ingestion pipeline logic."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.models.validators import (
    CircuitData,
    ConstructorData,
    DriverData,
    RaceData,
    SessionData,
    TelemetryData,
)
from src.pipeline.ingest import _upsert_batch, ingest_season, ingest_telemetry


class TestUpsertBatch:
    """Test the generic upsert helper with a mock session."""

    @patch("src.pipeline.ingest.sa_inspect")
    def test_empty_rows_returns_zero(self, mock_inspect, mock_session):
        from src.db.schema import Driver

        count = _upsert_batch(mock_session, Driver, [], ["driver_ref"])
        assert count == 0
        mock_session.execute.assert_not_called()

    @patch("src.pipeline.ingest.sa_inspect")
    @patch("src.pipeline.ingest.pg_insert")
    def test_single_batch_calls_execute(self, mock_pg_insert, mock_inspect, mock_session):
        from src.db.schema import Season

        mock_mapper = MagicMock()
        mock_col = MagicMock()
        mock_col.key = "url"
        mock_mapper.column_attrs = [mock_col]
        mock_inspect.return_value = mock_mapper

        mock_stmt = MagicMock()
        mock_pg_insert.return_value = mock_stmt
        mock_stmt.values.return_value = mock_stmt
        mock_stmt.on_conflict_do_update.return_value = mock_stmt
        mock_stmt.excluded = {"url": "x"}

        rows = [{"year": 2023, "url": "http://example.com"}]
        count = _upsert_batch(mock_session, Season, rows, ["year"])

        assert count == 1
        mock_session.execute.assert_called_once()
        mock_session.flush.assert_called_once()


class TestIngestSeason:
    @patch("src.pipeline.ingest.get_session")
    @patch("src.pipeline.ingest.ErgastClient")
    def test_ingest_season_calls_all_endpoints(self, mock_ergast_cls, mock_get_session):
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        mock_ergast = MagicMock()
        mock_ergast_cls.return_value.__enter__ = MagicMock(return_value=mock_ergast)
        mock_ergast_cls.return_value.__exit__ = MagicMock(return_value=False)

        # Return minimal data
        mock_ergast.get_drivers.return_value = [
            DriverData(driver_ref="ver", forename="Max", surname="Verstappen")
        ]
        mock_ergast.get_constructors.return_value = [
            ConstructorData(constructor_ref="red_bull", name="Red Bull")
        ]
        mock_ergast.get_circuits.return_value = [
            CircuitData(circuit_ref="bahrain", name="Bahrain International Circuit")
        ]
        mock_ergast.get_races.return_value = []

        # Mock the query chain for race ID lookup
        mock_session.query.return_value.filter.return_value.all.return_value = []

        with patch("src.pipeline.ingest._upsert_batch", return_value=1) as mock_upsert:
            counts = ingest_season(2023)

        assert "seasons" in counts
        assert "drivers" in counts
        assert "constructors" in counts
        assert "circuits" in counts
        mock_ergast.get_drivers.assert_called_once_with(2023)
        mock_ergast.get_constructors.assert_called_once_with(2023)


class TestIngestTelemetry:
    @patch("src.pipeline.ingest.get_session")
    @patch("src.pipeline.ingest.OpenF1Client")
    def test_ingest_telemetry_specific_keys(self, mock_openf1_cls, mock_get_session):
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        mock_openf1 = MagicMock()
        mock_openf1_cls.return_value.__enter__ = MagicMock(return_value=mock_openf1)
        mock_openf1_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_openf1.get_sessions.return_value = [
            SessionData(session_key=9001, year=2023)
        ]
        mock_openf1.get_car_data.return_value = []

        with patch("src.pipeline.ingest._upsert_batch", return_value=0):
            counts = ingest_telemetry(2023, session_keys=[9001])

        assert "sessions" in counts
        assert "telemetry_samples" in counts
        mock_openf1.get_car_data.assert_called_once_with(9001)
