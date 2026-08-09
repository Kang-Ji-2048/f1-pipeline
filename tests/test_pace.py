"""Tests for pace-metric logic (pure functions)."""

from __future__ import annotations

from src.analysis.pace import pace_metrics


class TestPaceMetrics:
    def test_empty(self):
        assert pace_metrics([]) == []

    def test_best_median_std_and_delta(self):
        rows = [
            {"driver_ref": "ver", "lap": 1, "time_millis": 91000},
            {"driver_ref": "ver", "lap": 2, "time_millis": 90000},
            {"driver_ref": "ham", "lap": 1, "time_millis": 92000},
            {"driver_ref": "ham", "lap": 2, "time_millis": 92000},
        ]
        metrics = pace_metrics(rows)

        # sorted by best lap, fastest first
        assert [m["driver_ref"] for m in metrics] == ["ver", "ham"]

        ver, ham = metrics
        assert ver["best_millis"] == 90000
        assert ver["median_millis"] == 90500
        assert ver["std_millis"] == 500.0
        assert ver["laps"] == 2
        assert ver["delta_millis"] == 0  # fastest overall

        assert ham["best_millis"] == 92000
        assert ham["std_millis"] == 0.0  # identical laps -> perfectly consistent
        assert ham["delta_millis"] == 2000  # 2s off the fastest lap
