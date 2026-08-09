"""Leakage-safe feature engineering for the race-points model.

Every feature for a given race uses only information available *before* that race
(the qualifying grid, or rolling/expanding stats over earlier races via a
``shift(1)``), so a model trained on these features never sees the outcome it is
trying to predict.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

# Feature columns fed to the model, in a fixed order.
FEATURE_COLUMNS: list[str] = [
    "grid_pos",  # qualifying position (known pre-race)
    "form_points",  # mean points over the driver's last N races
    "form_position",  # mean finishing position over the last N races
    "season_avg_points",  # driver's season-to-date average points
    "constructor_form",  # constructor's average points to date (car pace)
    "circuit_avg_points",  # driver's average points at this circuit historically
]

TARGET_COLUMN = "points"
_ID_COLUMNS = ["season", "round", "date", "circuit_ref", "driver_ref", "constructor_ref"]


def build_features(rows: list[dict[str, Any]], form_window: int = 3) -> pd.DataFrame:
    """Turn raw result rows into a feature matrix (+ target), leakage-safe.

    Returns a DataFrame with the id columns, the ``FEATURE_COLUMNS`` and the
    ``points`` target, ordered by date. ``rows`` are as produced by
    ``F1Database.get_results_frame``. An empty input yields an empty, correctly
    typed frame.
    """
    columns = _ID_COLUMNS + FEATURE_COLUMNS + [TARGET_COLUMN]
    if not rows:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(rows)
    df = df.sort_values(["date", "round", "driver_ref"]).reset_index(drop=True)

    df["points"] = df["points"].astype(float)
    df["grid_pos"] = df["grid"].fillna(20).astype(float)
    finish = df["position"].fillna(20).astype(float)
    df["_finish"] = finish

    # Driver recent form — previous races only (shift(1) drops the current race).
    df["form_points"] = df.groupby("driver_ref")["points"].transform(
        lambda s: s.shift(1).rolling(form_window, min_periods=1).mean()
    )
    df["form_position"] = df.groupby("driver_ref")["_finish"].transform(
        lambda s: s.shift(1).rolling(form_window, min_periods=1).mean()
    )
    # Driver season-to-date average points (expanding, shifted).
    df["season_avg_points"] = df.groupby(["season", "driver_ref"])["points"].transform(
        lambda s: s.shift(1).expanding().mean()
    )
    # Constructor form — average points to date (car competitiveness).
    df["constructor_form"] = df.groupby("constructor_ref")["points"].transform(
        lambda s: s.shift(1).expanding().mean()
    )
    # Driver history at this specific circuit.
    df["circuit_avg_points"] = df.groupby(["driver_ref", "circuit_ref"])["points"].transform(
        lambda s: s.shift(1).expanding().mean()
    )

    # First-appearance rows have no history: fall back to neutral defaults.
    defaults = {
        "form_points": 0.0,
        "form_position": 20.0,
        "season_avg_points": 0.0,
        "constructor_form": 0.0,
        "circuit_avg_points": 0.0,
    }
    df = df.fillna(defaults)

    return df[_ID_COLUMNS + FEATURE_COLUMNS + [TARGET_COLUMN]]
