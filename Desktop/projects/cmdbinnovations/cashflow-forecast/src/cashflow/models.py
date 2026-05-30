"""Two-model pipeline: lag-days regressor + realization-rate regressor.

Both use sklearn GradientBoostingRegressor with quantile loss to produce p10/p50/p90
estimates per claim, which propagate into the cash-forecast confidence bands.

Why sklearn over LightGBM here: zero native deps (no libomp), portable to any host
Yash spins up. Swap to LightGBM later if dataset size demands it.
"""
from __future__ import annotations

from dataclasses import dataclass

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from .features import CATEGORICAL, NUMERIC, build_features, feature_columns

QUANTILES = (0.1, 0.5, 0.9)


def _make_pipeline(alpha: float) -> Pipeline:
    pre = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
            ("num", "passthrough", NUMERIC),
        ]
    )
    model = GradientBoostingRegressor(
        loss="quantile",
        alpha=alpha,
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        min_samples_leaf=30,
        random_state=42,
    )
    return Pipeline([("pre", pre), ("model", model)])


def _train_quantile_set(X: pd.DataFrame, y: pd.Series) -> dict[float, Pipeline]:
    models: dict[float, Pipeline] = {}
    for q in QUANTILES:
        pipe = _make_pipeline(alpha=q)
        pipe.fit(X, y)
        models[q] = pipe
    return models


def _predict_quantiles(models: dict[float, Pipeline], X: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {f"p{int(q*100)}": models[q].predict(X) for q in QUANTILES},
        index=X.index,
    )


@dataclass
class TrainedModels:
    lag_models: dict[float, Pipeline]
    realization_models: dict[float, Pipeline]
    metrics: dict[str, float]

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """Predict per-claim lag-days and realization-rate (p10/p50/p90 each)."""
        X = build_features(df)[feature_columns()]
        lag = _predict_quantiles(self.lag_models, X).add_prefix("lag_")
        real = _predict_quantiles(self.realization_models, X).add_prefix("real_")
        for c in real.columns:
            real[c] = real[c].clip(0.0, 1.0)
        for c in lag.columns:
            lag[c] = lag[c].clip(lower=1.0)
        # Enforce monotonic p10 <= p50 <= p90 (quantile crossing safeguard)
        lag["lag_p10"] = np.minimum(lag["lag_p10"], lag["lag_p50"])
        lag["lag_p90"] = np.maximum(lag["lag_p90"], lag["lag_p50"])
        real["real_p10"] = np.minimum(real["real_p10"], real["real_p50"])
        real["real_p90"] = np.maximum(real["real_p90"], real["real_p50"])
        return pd.concat([lag, real], axis=1)

    def save(self, path: str) -> None:
        joblib.dump(self, path)

    @staticmethod
    def load(path: str) -> "TrainedModels":
        return joblib.load(path)


def time_based_split(
    resolved: pd.DataFrame, holdout_frac: float = 0.2
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Train on older claims, evaluate on the most recent `holdout_frac`."""
    ordered = resolved.sort_values("submission_date").reset_index(drop=True)
    cut = int(len(ordered) * (1 - holdout_frac))
    return ordered.iloc[:cut].copy(), ordered.iloc[cut:].copy()


def train(resolved: pd.DataFrame) -> TrainedModels:
    train_df, test_df = time_based_split(resolved)

    X_train = build_features(train_df)[feature_columns()]
    X_test = build_features(test_df)[feature_columns()]

    lag_models = _train_quantile_set(X_train, train_df["lag_days"])
    real_models = _train_quantile_set(X_train, train_df["realization_rate"])

    lag_pred = lag_models[0.5].predict(X_test)
    real_pred = real_models[0.5].predict(X_test)

    metrics = {
        "n_train": float(len(train_df)),
        "n_test": float(len(test_df)),
        "lag_mae_days": float(np.mean(np.abs(lag_pred - test_df["lag_days"]))),
        "lag_rmse_days": float(np.sqrt(np.mean((lag_pred - test_df["lag_days"]) ** 2))),
        "real_mae": float(np.mean(np.abs(real_pred - test_df["realization_rate"]))),
        "dollar_mape": float(
            np.mean(
                np.abs(
                    (real_pred - test_df["realization_rate"]) * test_df["billed_amount"]
                )
                / test_df["billed_amount"]
            )
        ),
    }
    return TrainedModels(lag_models, real_models, metrics)
