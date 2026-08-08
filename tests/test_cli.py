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
