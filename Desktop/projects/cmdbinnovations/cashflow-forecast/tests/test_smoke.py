"""Smoke test: end-to-end pipeline runs and produces sensible outputs."""
from pathlib import Path

from cashflow.pipeline import run


def test_end_to_end(tmp_path, monkeypatch):
    metrics = run()
    assert metrics["n_train"] > 0
    assert metrics["n_test"] > 0
    assert metrics["lag_mae_days"] < 30  # ballpark sanity
    assert 0 <= metrics["real_mae"] <= 1

    root = Path(__file__).resolve().parents[1]
    assert (root / "artifacts" / "models.joblib").exists()
    assert (root / "data" / "forecast_weekly.csv").exists()
