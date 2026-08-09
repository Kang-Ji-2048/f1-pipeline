"""Tests for leakage-safe feature engineering."""

from __future__ import annotations

from src.ml.features import FEATURE_COLUMNS, build_features


def _row(season, rnd, date, circuit, driver, constructor, grid, position, points):
    return {
        "season": season,
        "round": rnd,
        "date": date,
        "circuit_ref": circuit,
        "driver_ref": driver,
        "constructor_ref": constructor,
        "grid": grid,
        "position": position,
        "points": points,
    }


class TestBuildFeatures:
    def test_empty_input_yields_empty_frame_with_columns(self):
        df = build_features([])
        assert list(df.columns)[-len(FEATURE_COLUMNS) - 1 :] == FEATURE_COLUMNS + ["points"]
        assert len(df) == 0

    def test_form_uses_only_previous_races(self):
        rows = [
            _row(2023, 1, "2023-03-01", "a", "ver", "rb", 1, 1, 25.0),
            _row(2023, 2, "2023-03-08", "b", "ver", "rb", 2, 2, 18.0),
            _row(2023, 3, "2023-03-15", "c", "ver", "rb", 1, 1, 25.0),
        ]
        df = build_features(rows, form_window=3).set_index("round")

        # Round 1: no prior race -> neutral defaults, and grid passes through.
        assert df.loc[1, "form_points"] == 0.0
        assert df.loc[1, "grid_pos"] == 1.0
        # Round 2: form = round-1 points only (25).
        assert df.loc[2, "form_points"] == 25.0
        # Round 3: form = mean of rounds 1 and 2 (25, 18) = 21.5 — never the
        # current race's own points (no leakage).
        assert df.loc[3, "form_points"] == 21.5
        assert df.loc[3, "season_avg_points"] == 21.5

    def test_target_and_features_present(self):
        rows = [_row(2023, 1, "2023-03-01", "a", "ver", "rb", 1, 1, 25.0)]
        df = build_features(rows)
        for col in FEATURE_COLUMNS + ["points"]:
            assert col in df.columns
        assert df.iloc[0]["points"] == 25.0
