"""Streamlit dashboard for Detox cash flow forecast."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ARTIFACTS = ROOT / "artifacts"

st.set_page_config(page_title="Detox Cash Flow Forecast", layout="wide")
st.title("💰 Detox Cash Flow Forecast")
st.caption("Phase 1 POC — synthetic data. Replace with real claims once available.")


@st.cache_data
def load_forecast(freq_name: str) -> pd.DataFrame:
    path = DATA / f"forecast_{freq_name}.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, parse_dates=["bucket"])
    return df


@st.cache_data
def load_per_claim() -> pd.DataFrame:
    path = DATA / "per_claim_forecast.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, parse_dates=["submission_date", "expected_pay_date"])


@st.cache_data
def load_metrics() -> dict:
    path = ARTIFACTS / "metrics.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


metrics = load_metrics()
if not metrics:
    st.warning("No trained model found. Run `python -m cashflow.pipeline` first.")
    st.stop()

# --- Top metrics row -----------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Held-out claims", f"{int(metrics['n_test']):,}")
c2.metric("Lag MAE (days)", f"{metrics['lag_mae_days']:.1f}")
c3.metric("Realization MAE", f"{metrics['real_mae']*100:.1f}%")
c4.metric("Dollar MAPE", f"{metrics['dollar_mape']*100:.1f}%")

st.divider()

# --- Forecast chart ------------------------------------------------------
freq_label = st.radio("Forecast granularity", ["Daily", "Weekly", "Monthly"], index=1, horizontal=True)
freq_map = {"Daily": "daily", "Weekly": "weekly", "Monthly": "monthly"}
fc = load_forecast(freq_map[freq_label])

if fc.empty:
    st.info("No forecast data found.")
    st.stop()

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=fc["bucket"], y=fc["cash_high"],
    name="p90 (optimistic)", line=dict(width=0), showlegend=False,
))
fig.add_trace(go.Scatter(
    x=fc["bucket"], y=fc["cash_low"],
    name="Confidence band", fill="tonexty", line=dict(width=0),
    fillcolor="rgba(64,128,255,0.20)",
))
fig.add_trace(go.Scatter(
    x=fc["bucket"], y=fc["expected_cash"],
    name="Expected cash", line=dict(color="#1f77b4", width=3),
))
fig.update_layout(
    title=f"{freq_label} expected cash collections (with p10–p90 band)",
    xaxis_title="Bucket start",
    yaxis_title="Cash ($)",
    height=480,
    hovermode="x unified",
)
st.plotly_chart(fig, use_container_width=True)

# --- Summary table -------------------------------------------------------
st.subheader(f"{freq_label} forecast detail")
display = fc.copy()
display["bucket"] = display["bucket"].dt.strftime("%Y-%m-%d")
for c in ["expected_cash", "cash_low", "cash_high"]:
    display[c] = display[c].round(0)
st.dataframe(display, use_container_width=True, hide_index=True)

# --- Per-claim drill-down ------------------------------------------------
st.divider()
st.subheader("Per-claim predictions (pending claims)")
pc = load_per_claim()
if not pc.empty:
    show = pc[[
        "claim_id", "submission_date", "payer", "claim_type",
        "billed_amount", "lag_p50", "real_p50",
        "expected_pay_date", "expected_cash", "cash_low", "cash_high",
    ]].copy()
    show["expected_pay_date"] = pd.to_datetime(show["expected_pay_date"]).dt.strftime("%Y-%m-%d")
    show["submission_date"] = pd.to_datetime(show["submission_date"]).dt.strftime("%Y-%m-%d")
    for c in ["billed_amount", "expected_cash", "cash_low", "cash_high"]:
        show[c] = show[c].round(0)
    show["real_p50"] = (show["real_p50"] * 100).round(1).astype(str) + "%"
    show["lag_p50"] = show["lag_p50"].round(0).astype(int)
    st.dataframe(show, use_container_width=True, hide_index=True)
