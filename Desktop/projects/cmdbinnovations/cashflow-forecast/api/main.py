"""FastAPI service exposing per-claim predictions and cash forecasts.

Endpoints:
    GET  /health
    GET  /accuracy        — held-out metrics from training
    POST /predict         — per-claim lag-days + realization predictions
    GET  /forecast        — bucketed cash forecast (?freq=D|W|M)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from cashflow.forecast import bucket_forecast, per_claim_forecast
from cashflow.models import TrainedModels
from cashflow.synth import split_resolved_pending

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
DATA = ROOT / "data"

app = FastAPI(title="Cash Flow Forecast — Detox POC", version="0.1.0")


def _models() -> TrainedModels:
    path = ARTIFACTS / "models.joblib"
    if not path.exists():
        raise HTTPException(
            status_code=503,
            detail="Models not trained yet. Run `python -m cashflow.pipeline` first.",
        )
    return TrainedModels.load(str(path))


def _claims() -> pd.DataFrame:
    path = DATA / "claims.csv"
    if not path.exists():
        raise HTTPException(status_code=503, detail="No claims data found.")
    return pd.read_csv(path, parse_dates=["submission_date", "paid_date"])


class ClaimIn(BaseModel):
    claim_id: str
    submission_date: str = Field(..., description="YYYY-MM-DD")
    payer: str
    claim_type: str
    in_network: bool
    billed_amount: float


class PredictRequest(BaseModel):
    claims: list[ClaimIn]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/accuracy")
def accuracy() -> dict:
    path = ARTIFACTS / "metrics.json"
    if not path.exists():
        raise HTTPException(status_code=503, detail="No metrics found.")
    return json.loads(path.read_text())


@app.post("/predict")
def predict(req: PredictRequest) -> list[dict]:
    m = _models()
    df = pd.DataFrame([c.model_dump() for c in req.claims])
    df["submission_date"] = pd.to_datetime(df["submission_date"])
    preds = m.predict(df)
    out = pd.concat([df[["claim_id"]], preds], axis=1)
    return out.to_dict(orient="records")


@app.get("/forecast")
def forecast(freq: Literal["D", "W", "M"] = "W") -> list[dict]:
    m = _models()
    claims = _claims()
    _, pending = split_resolved_pending(claims)
    if pending.empty:
        return []
    preds = m.predict(pending)
    per_claim = per_claim_forecast(pending, preds)
    agg = bucket_forecast(per_claim, freq=freq)
    agg["bucket"] = agg["bucket"].dt.strftime("%Y-%m-%d")
    return agg.to_dict(orient="records")
