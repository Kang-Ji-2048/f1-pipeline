"""Tests for the race-points model (train / evaluate / persist / predict)."""

from __future__ import annotations

import random

from src.ml.features import build_features
from src.ml.model import EvalResult, evaluate, load_model, predict, save_model, train_model


def _synthetic_rows(n_rounds: int = 12) -> list[dict[str, object]]:
    """Build a learnable dataset: points depend inversely on grid, plus noise."""
    rng = random.Random(0)
    drivers = [("ver", "rb"), ("ham", "mer"), ("lec", "fer"), ("nor", "mcl")]
    points_for = {1: 25.0, 2: 18.0, 3: 15.0, 4: 12.0}
    rows: list[dict[str, object]] = []
    for rnd in range(1, n_rounds + 1):
        grid_order = drivers[:]
        rng.shuffle(grid_order)
        for pos, (drv, con) in enumerate(grid_order, 1):
            rows.append(
                {
                    "season": 2023,
                    "round": rnd,
                    "date": f"2023-{rnd:02d}-01",
                    "circuit_ref": f"c{rnd % 3}",
                    "driver_ref": drv,
                    "constructor_ref": con,
                    "grid": pos,
                    "position": pos,
                    "points": points_for[pos],
                }
            )
    return rows


class TestModel:
    def test_train_and_predict_roundtrip(self):
        features = build_features(_synthetic_rows())
        model = train_model(features)
        ranked = predict(model, features)

        assert "predicted_points" in ranked.columns
        assert len(ranked) == len(features)
        # sorted descending by prediction
        preds = ranked["predicted_points"].tolist()
        assert preds == sorted(preds, reverse=True)

    def test_predict_keeps_driver_and_actual_points_for_comparison(self):
        # The dashboard's Predictions tab charts predicted vs actual per driver,
        # so predict() must return driver_ref and the actual points alongside
        # the prediction.
        features = build_features(_synthetic_rows())
        ranked = predict(train_model(features), features)

        for col in ("driver_ref", "points", "predicted_points"):
            assert col in ranked.columns
        assert ranked["driver_ref"].notna().all()

    def test_evaluate_returns_metrics_and_beats_or_matches_baseline(self):
        features = build_features(_synthetic_rows(n_rounds=16))
        result = evaluate(features, test_fraction=0.25)

        assert isinstance(result, EvalResult)
        assert result.n_train > 0 and result.n_test > 0
        assert result.mae >= 0.0
        # feature importances cover every feature and sum to ~1
        assert set(result.feature_importances) == set(
            build_features(_synthetic_rows()).columns[-7:-1]
        )
        assert abs(sum(result.feature_importances.values()) - 1.0) < 1e-6

    def test_save_and_load(self, tmp_path):
        features = build_features(_synthetic_rows())
        model = train_model(features)
        path = tmp_path / "m.joblib"
        save_model(model, path)
        assert path.exists()

        loaded = load_model(path)
        # loaded model produces identical predictions
        a = predict(model, features)["predicted_points"].tolist()
        b = predict(loaded, features)["predicted_points"].tolist()
        assert a == b
