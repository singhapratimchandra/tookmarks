# Cash Flow Forecasting — Detox POC

Predicts per-claim **payment lag (days)** and **realization rate (paid / billed)** for the
Detox facility, then rolls per-claim predictions into **daily / weekly / monthly cash
forecasts** with confidence bands.

This is the Phase 1 proof of concept agreed in the initial discovery call (May 2026).
Lab and Clinics plug into the same architecture in later phases.

---

## Quickstart

```bash
# 1. Install
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Generate synthetic Detox data + train models + write artifacts
python -m cashflow.pipeline

# 3. Launch API (port 8000)
uvicorn api.main:app --reload --port 8000

# 4. Launch dashboard (port 8501) — in a separate terminal
streamlit run dashboard/app.py
```

Open http://localhost:8501 for the forecast dashboard.

---

## Project Layout

```
cashflow-forecast/
├── src/cashflow/         # Library: data, models, forecast aggregator
│   ├── synth.py          # Synthetic Detox claims generator
│   ├── features.py       # Feature engineering
│   ├── models.py         # Lag-days + realization-rate models
│   ├── forecast.py       # Per-claim → time-bucket cash forecast
│   └── pipeline.py       # End-to-end: generate → train → save artifacts
├── api/main.py           # FastAPI service
├── dashboard/app.py      # Streamlit dashboard
├── artifacts/            # Trained models + held-out metrics (generated)
├── data/                 # Synthetic CSVs (generated)
└── tests/                # Smoke tests
```

---

## Modeling approach

Two independent regressors, each with prediction intervals:

1. **Lag-days model** — predicts days from claim submission to payment posted.
2. **Realization-rate model** — predicts `paid_amount / billed_amount` (a rate, not a
   raw dollar, so it generalises across claim sizes).

**Time-based train/test split.** Training uses older claims; evaluation uses a held-out
later window. This mirrors real-world deployment and avoids look-ahead leakage.

**Right-censoring handled.** Still-pending claims are excluded from training but scored
at inference time — their predicted payment dates contribute to the forecast.

**Confidence bands.** Quantile regression (LightGBM) yields p10/p50/p90 estimates per
claim, which are summed to give forecast confidence bands per time bucket.

---

## Deliverable status (per MoM)

| Requirement | Status |
|---|---|
| Predictive model — Detox | ✅ POC |
| Daily / weekly / monthly granularity | ✅ |
| All-claim coverage | ✅ |
| Continuous learning | ⏳ Retraining hook stubbed; cron in Phase 1.5 |
| Hosted web app + dashboard | ✅ Local; Yash to host |
| Lab + Clinics | ⏳ Phase 2 / 3 |

---

## Handoff notes for Yash (CTO, Remote Life Health)

- Stateless FastAPI + Streamlit; both can run behind a single reverse proxy.
- Models persisted via `joblib` to `artifacts/`. Swap in S3 / blob storage in prod.
- Replace `cashflow.synth` with the real claims loader once data lands.
