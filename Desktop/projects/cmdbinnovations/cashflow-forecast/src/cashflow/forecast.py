"""Roll per-claim predictions into time-bucketed cash forecasts.

For each pending claim we have p10/p50/p90 on both lag-days and realization-rate.
The expected payment date = submission_date + p50_lag. The expected dollars = billed
* p50_real, with p10/p90 dollar bounds. We then bucket by day/week/month.
"""
from __future__ import annotations

from datetime import timedelta

import pandas as pd


def per_claim_forecast(
    pending: pd.DataFrame, predictions: pd.DataFrame
) -> pd.DataFrame:
    """Join predictions with pending claims and compute expected payment dates/dollars."""
    df = pending.join(predictions)
    sub = pd.to_datetime(df["submission_date"])
    df["expected_pay_date"] = sub + pd.to_timedelta(df["lag_p50"].round(), unit="D")
    df["pay_date_low"] = sub + pd.to_timedelta(df["lag_p10"].round(), unit="D")
    df["pay_date_high"] = sub + pd.to_timedelta(df["lag_p90"].round(), unit="D")
    df["expected_cash"] = df["billed_amount"] * df["real_p50"]
    df["cash_low"] = df["billed_amount"] * df["real_p10"]
    df["cash_high"] = df["billed_amount"] * df["real_p90"]
    return df


def bucket_forecast(
    per_claim: pd.DataFrame, freq: str = "W"
) -> pd.DataFrame:
    """Aggregate per-claim forecasts into a time-bucket cash projection.

    freq: 'D' daily, 'W' weekly, 'M' monthly (pandas offset aliases).
    Returns one row per bucket with expected/low/high cash totals.
    """
    g = per_claim.copy()
    g["bucket"] = pd.to_datetime(g["expected_pay_date"]).dt.to_period(freq).dt.start_time
    agg = (
        g.groupby("bucket")
        .agg(
            expected_cash=("expected_cash", "sum"),
            cash_low=("cash_low", "sum"),
            cash_high=("cash_high", "sum"),
            n_claims=("claim_id", "count"),
        )
        .reset_index()
        .sort_values("bucket")
    )
    return agg
