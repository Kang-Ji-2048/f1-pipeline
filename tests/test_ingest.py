"""Tests for the ingestion pipeline logic."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.models.validators import (
    CircuitData,
    ConstructorData,
    DriverData,
    SessionData,
    TelemetryData,
)
from src.pipeline.ingest import (
    _upsert_batch,
    ingest_live,
    ingest_season,
    ingest_telemetry,
)


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

        with patch("src.pipeline.ingest._upsert_batch", return_value=1):
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
    def test_ingest_telemetry_chunks_per_driver_and_commits_per_session(
        self, mock_openf1_cls, mock_get_session
    ):
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        mock_openf1 = MagicMock()
        mock_openf1_cls.return_value.__enter__ = MagicMock(return_value=mock_openf1)
        mock_openf1_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_openf1.get_sessions.return_value = [SessionData(session_key=9001, year=2023)]
        mock_openf1.get_session_drivers.return_value = [1, 44]
        mock_openf1.get_car_data.return_value = []

        with patch("src.pipeline.ingest._upsert_batch", return_value=0):
            counts = ingest_telemetry(2023, session_keys=[9001])

        assert "sessions" in counts
        assert "telemetry_samples" in counts
        # telemetry is fetched one driver at a time (bounded request size)
        mock_openf1.get_session_drivers.assert_called_once_with(9001)
        assert mock_openf1.get_car_data.call_count == 2
        mock_openf1.get_car_data.assert_any_call(9001, driver_number=1)
        mock_openf1.get_car_data.assert_any_call(9001, driver_number=44)
        # progress is committed per session, not once at the very end
        assert mock_session.commit.call_count >= 1

    @patch("src.pipeline.ingest.get_session")
    @patch("src.pipeline.ingest.OpenF1Client")
    def test_ingest_telemetry_skip_existing_skips_done_sessions(
        self, mock_openf1_cls, mock_get_session
    ):
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)
        # session 9001 already has telemetry rows in the DB
        mock_session.query.return_value.distinct.return_value.all.return_value = [(9001,)]

        mock_openf1 = MagicMock()
        mock_openf1_cls.return_value.__enter__ = MagicMock(return_value=mock_openf1)
        mock_openf1_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_openf1.get_sessions.return_value = [
            SessionData(session_key=9001, year=2023),
            SessionData(session_key=9002, year=2023),
        ]
        mock_openf1.get_session_drivers.return_value = [1]
        mock_openf1.get_car_data.return_value = []

        with patch("src.pipeline.ingest._upsert_batch", return_value=0):
            ingest_telemetry(2023, skip_existing=True)

        # only the not-yet-ingested session is processed
        mock_openf1.get_session_drivers.assert_called_once_with(9002)


class TestIngestLive:
    @patch("src.pipeline.ingest.get_session")
    def test_ingest_live_polls_incrementally(self, mock_get_session):
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        batch1 = [
            TelemetryData(session_key=9001, driver_number=1, date="2023-03-05T15:01:00"),
            TelemetryData(session_key=9001, driver_number=1, date="2023-03-05T15:01:01"),
        ]
        batch2 = [
            TelemetryData(session_key=9001, driver_number=1, date="2023-03-05T15:01:02"),
        ]
        fake_client = MagicMock()
        fake_client.get_latest_car_data.side_effect = [batch1, batch2]

        sleep_calls: list[float] = []

        with patch("src.pipeline.ingest._upsert_batch", side_effect=[2, 1]):
            counts = ingest_live(
                session_key=9001,
                interval=0.0,
                max_iterations=2,
                client=fake_client,
                sleep=sleep_calls.append,
            )

        assert counts["telemetry_samples"] == 3
        assert counts["iterations"] == 2

        calls = fake_client.get_latest_car_data.call_args_list
        assert calls[0].kwargs.get("after") is None
        # second poll uses the max date from the first batch as its cursor
        assert calls[1].kwargs["after"] == "2023-03-05T15:01:01"
        # injected client is never closed by ingest_live
        fake_client.close.assert_not_called()

    @patch("src.pipeline.ingest.get_session")
    def test_ingest_live_handles_empty_poll(self, mock_get_session):
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        fake_client = MagicMock()
        fake_client.get_latest_car_data.return_value = []

        with patch("src.pipeline.ingest._upsert_batch") as mock_upsert:
            counts = ingest_live(
                session_key="latest",
                interval=0.0,
                max_iterations=1,
                client=fake_client,
                sleep=lambda _s: None,
            )

        assert counts == {"telemetry_samples": 0, "iterations": 1}
        mock_upsert.assert_not_called()


class TestWarnZeroCounts:
    def test_flags_only_zero_row_tables(self):
        from src.pipeline.ingest import _warn_zero_counts

        warnings = _warn_zero_counts({"drivers": 20, "lap_times": 0, "pit_stops": 0, "races": 24})
        assert warnings == ["lap_times ingested 0 rows", "pit_stops ingested 0 rows"]

    def test_empty_when_all_populated(self):
        from src.pipeline.ingest import _warn_zero_counts

        assert _warn_zero_counts({"drivers": 20, "races": 24}) == []
