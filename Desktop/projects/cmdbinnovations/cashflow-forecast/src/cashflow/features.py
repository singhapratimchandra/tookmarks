"""Feature engineering for the two regressors."""
from __future__ import annotations

import pandas as pd

CATEGORICAL = ["payer", "claim_type"]
NUMERIC = ["billed_amount", "in_network_int", "sub_dow", "sub_month"]


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Return a feature frame aligned with the input index."""
    out = pd.DataFrame(index=df.index)
    sub = pd.to_datetime(df["submission_date"])
    out["billed_amount"] = df["billed_amount"].astype(float)
    out["in_network_int"] = df["in_network"].astype(int)
    out["sub_dow"] = sub.dt.dayofweek
    out["sub_month"] = sub.dt.month
    out["payer"] = df["payer"].astype(str)
    out["claim_type"] = df["claim_type"].astype(str)
    return out


def feature_columns() -> list[str]:
    return NUMERIC + CATEGORICAL
