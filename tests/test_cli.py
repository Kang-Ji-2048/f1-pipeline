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
