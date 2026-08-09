"""Train, evaluate, persist and apply the race-points model.

A gradient-boosting regressor predicts the points a driver will score in a race
from the leakage-safe features in :mod:`src.ml.features`. Evaluation uses a
time-ordered split (train on earlier races, test on later ones) so the reported
error reflects genuine forecasting, and a linear model is scored as a baseline.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score

from src.ml.features import FEATURE_COLUMNS, TARGET_COLUMN

DEFAULT_MODEL_PATH = Path("models/points_model.joblib")


@dataclass
class EvalResult:
    """Metrics from a time-ordered hold-out evaluation."""

    mae: float
    r2: float
    baseline_mae: float
    n_train: int
    n_test: int
    feature_importances: dict[str, float]


def train_model(features: pd.DataFrame) -> Any:
    """Fit and return a gradient-boosting regressor on the given feature frame."""
    model = GradientBoostingRegressor(random_state=0)
    model.fit(features[FEATURE_COLUMNS], features[TARGET_COLUMN])
    return model


def evaluate(features: pd.DataFrame, test_fraction: float = 0.2) -> EvalResult:
    """Time-ordered hold-out evaluation: train on earlier races, test on later.

    The frame is assumed already ordered by date (as ``build_features`` returns
    it). Compares the model's MAE against a linear-regression baseline.
    """
    n = len(features)
    split = max(1, int(n * (1 - test_fraction)))
    train, test = features.iloc[:split], features.iloc[split:]
    if len(test) == 0:  # too few rows to hold any out
        train, test = features.iloc[:-1], features.iloc[-1:]

    model = train_model(train)
    preds = model.predict(test[FEATURE_COLUMNS])
    baseline = (
        LinearRegression()
        .fit(train[FEATURE_COLUMNS], train[TARGET_COLUMN])
        .predict(test[FEATURE_COLUMNS])
    )
    importances = {col: float(imp) for col, imp in zip(FEATURE_COLUMNS, model.feature_importances_)}
    return EvalResult(
        mae=float(mean_absolute_error(test[TARGET_COLUMN], preds)),
        r2=float(r2_score(test[TARGET_COLUMN], preds)) if len(test) > 1 else float("nan"),
        baseline_mae=float(mean_absolute_error(test[TARGET_COLUMN], baseline)),
        n_train=int(len(train)),
        n_test=int(len(test)),
        feature_importances=importances,
    )


def save_model(model: Any, path: Path = DEFAULT_MODEL_PATH) -> Path:
    """Persist a trained model to ``path`` (creating parent dirs)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)
    return path


def load_model(path: Path = DEFAULT_MODEL_PATH) -> Any:
    """Load a model previously saved with :func:`save_model`."""
    return joblib.load(path)


def predict(model: Any, features: pd.DataFrame) -> pd.DataFrame:
    """Return ``features`` with a ``predicted_points`` column, ranked descending."""
    out = features.copy()
    out["predicted_points"] = model.predict(out[FEATURE_COLUMNS])
    return out.sort_values("predicted_points", ascending=False).reset_index(drop=True)
