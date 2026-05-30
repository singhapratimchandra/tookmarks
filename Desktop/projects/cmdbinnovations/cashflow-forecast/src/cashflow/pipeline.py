"""End-to-end: synth -> train -> forecast -> persist artifacts."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .forecast import bucket_forecast, per_claim_forecast
from .models import TrainedModels, train
from .synth import generate_claims, split_resolved_pending

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
ARTIFACTS = ROOT / "artifacts"


def run() -> dict:
    DATA.mkdir(exist_ok=True)
    ARTIFACTS.mkdir(exist_ok=True)

    print("[1/4] Generating synthetic Detox claims...")
    claims = generate_claims()
    claims.to_csv(DATA / "claims.csv", index=False)

    resolved, pending = split_resolved_pending(claims)
    print(f"      resolved={len(resolved)}  pending={len(pending)}")

    print("[2/4] Training models (time-based split)...")
    models: TrainedModels = train(resolved)
    models.save(str(ARTIFACTS / "models.joblib"))
    (ARTIFACTS / "metrics.json").write_text(json.dumps(models.metrics, indent=2))
    print("      metrics:", models.metrics)

    print("[3/4] Forecasting pending claims...")
    preds = models.predict(pending)
    per_claim = per_claim_forecast(pending, preds)
    per_claim.to_csv(DATA / "per_claim_forecast.csv", index=False)

    print("[4/4] Aggregating to day/week/month buckets...")
    for freq, name in [("D", "daily"), ("W", "weekly"), ("M", "monthly")]:
        agg = bucket_forecast(per_claim, freq=freq)
        agg.to_csv(DATA / f"forecast_{name}.csv", index=False)
        print(f"      wrote forecast_{name}.csv  ({len(agg)} buckets)")

    return models.metrics


if __name__ == "__main__":
    run()
