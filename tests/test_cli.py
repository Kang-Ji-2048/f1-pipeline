"""Tests for the CLI entrypoint."""

from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from src.pipeline.cli import main


class TestLiveCommand:
    def test_live_invokes_ingest_live_with_options(self):
        runner = CliRunner()
        with patch("src.pipeline.cli.ingest_live") as mock_live:
            mock_live.return_value = {"telemetry_samples": 3, "iterations": 2}
            result = runner.invoke(
                main,
                ["live", "--session-key", "9001", "--interval", "1", "--max-iterations", "2"],
            )

        assert result.exit_code == 0
        mock_live.assert_called_once_with(session_key="9001", interval=1.0, max_iterations=2)
        assert "telemetry_samples: 3" in result.output

    def test_live_defaults_to_latest(self):
        runner = CliRunner()
        with patch("src.pipeline.cli.ingest_live") as mock_live:
            mock_live.return_value = {"telemetry_samples": 0, "iterations": 1}
            result = runner.invoke(main, ["live", "--max-iterations", "1"])

        assert result.exit_code == 0
        _, kwargs = mock_live.call_args
        assert kwargs["session_key"] == "latest"
        assert kwargs["max_iterations"] == 1


class TestIngestOpenF1Command:
    def test_skip_existing_flag_passed_through(self):
        runner = CliRunner()
        with patch("src.pipeline.cli.ingest_telemetry") as mock_ingest:
            mock_ingest.return_value = {"sessions": 0, "telemetry_samples": 0}
            result = runner.invoke(main, ["ingest-openf1", "--year", "2024", "--skip-existing"])

        assert result.exit_code == 0
        _, kwargs = mock_ingest.call_args
        assert kwargs["skip_existing"] is True


class TestBackfillCommand:
    def test_backfill_sums_totals_across_seasons(self):
        runner = CliRunner()
        with patch("src.pipeline.cli.backfill_seasons") as mock_backfill:
            mock_backfill.return_value = {
                2022: {"races": 22, "race_results": 440},
                2023: {"races": 23, "race_results": 460},
            }
            result = runner.invoke(main, ["backfill", "--start", "2022", "--end", "2023"])

        assert result.exit_code == 0, result.output
        assert "Backfilled 2/2 seasons" in result.output
        assert "races: 45 rows" in result.output  # 22 + 23
        _, kwargs = mock_backfill.call_args
        assert kwargs["continue_on_error"] is True

    def test_backfill_reports_skipped_seasons(self):
        runner = CliRunner()
        with patch("src.pipeline.cli.backfill_seasons") as mock_backfill:
            mock_backfill.return_value = {2022: {"races": 22}}  # 2023 failed
            result = runner.invoke(main, ["backfill", "--start", "2022", "--end", "2023"])

        assert result.exit_code == 0
        assert "failed (skipped): 2023" in result.output

    def test_backfill_rejects_reversed_range(self):
        runner = CliRunner()
        result = runner.invoke(main, ["backfill", "--start", "2023", "--end", "2020"])
        assert result.exit_code == 1
        assert "must be >= --start" in result.output


class TestAggregateTelemetryCommand:
    def test_reports_summary_row_count(self):
        runner = CliRunner()
        with (
            patch("src.pipeline.cli.get_session") as mock_get_session,
            patch("src.pipeline.cli.aggregate_telemetry", return_value=40) as mock_agg,
        ):
            mock_get_session.return_value.__enter__.return_value = object()
            mock_get_session.return_value.__exit__.return_value = False
            result = runner.invoke(main, ["aggregate-telemetry"])

        assert result.exit_code == 0, result.output
        assert "Wrote 40 telemetry summary rows" in result.output
        mock_agg.assert_called_once()


class TestExportS3Command:
    def test_errors_when_no_bucket(self):
        runner = CliRunner()
        with patch("src.pipeline.cli.settings") as mock_settings:
            mock_settings.S3_BUCKET = ""
            mock_settings.S3_PREFIX = "f1-pipeline"
            result = runner.invoke(main, ["export-s3", "--season", "2024"])

        assert result.exit_code == 1
        assert "no S3 bucket" in result.output

    def test_exports_with_explicit_bucket(self):
        runner = CliRunner()
        with (
            patch("src.pipeline.cli.F1Database") as mock_db_cls,
            patch("src.pipeline.export.export_to_s3") as mock_export,
        ):
            mock_db = mock_db_cls.return_value.__enter__.return_value
            mock_db.get_driver_standings.return_value = []
            mock_db.get_constructor_standings.return_value = []
            mock_db.get_races.return_value = []
            mock_export.return_value = ["f1/2024/races.csv"]

            result = runner.invoke(main, ["export-s3", "--season", "2024", "--bucket", "my-bucket"])

        assert result.exit_code == 0
        assert "f1/2024/races.csv" in result.output
        args, _ = mock_export.call_args
        assert args[1] == "my-bucket"


class TestTrainModelCommand:
    def test_trains_and_reports_metrics(self, tmp_path):
        from tests.test_model import _synthetic_rows

        runner = CliRunner()
        with (
            patch("src.pipeline.cli.F1Database") as mock_db_cls,
            patch("src.ml.model.save_model") as mock_save,
        ):
            mock_db = mock_db_cls.return_value.__enter__.return_value
            mock_db.get_results_frame.return_value = _synthetic_rows(14)
            mock_save.return_value = tmp_path / "m.joblib"
            result = runner.invoke(main, ["train-model", "--test-fraction", "0.25"])

        assert result.exit_code == 0, result.output
        assert "Model trained on" in result.output
        assert "MAE" in result.output

    def test_errors_with_insufficient_data(self):
        runner = CliRunner()
        with patch("src.pipeline.cli.F1Database") as mock_db_cls:
            mock_db = mock_db_cls.return_value.__enter__.return_value
            mock_db.get_results_frame.return_value = []
            result = runner.invoke(main, ["train-model"])

        assert result.exit_code == 1
        assert "Not enough data" in result.output


class TestPredictCommand:
    def test_errors_without_trained_model(self):
        runner = CliRunner()
        with patch("src.ml.model.DEFAULT_MODEL_PATH") as mock_path:
            mock_path.exists.return_value = False
            result = runner.invoke(main, ["predict", "--season", "2023", "--round", "1"])

        assert result.exit_code == 1
        assert "No trained model" in result.output
