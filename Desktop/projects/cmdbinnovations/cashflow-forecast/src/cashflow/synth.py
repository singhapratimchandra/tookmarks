"""Synthetic Detox claims generator.

Mirrors the structure Sam described in the discovery call:
- ~85-90% insurance, 10-15% patient pay
- Per-diem / case-rate billing
- Bills at 2-3x Medicare; each payer pays their contracted rate
- Variable lag (days) and realization (paid/billed) per payer
- Right-censored tail: most recent claims have not paid yet

Replace this module with a real-data loader once Sam's Detox export arrives.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

RNG = np.random.default_rng(42)


@dataclass(frozen=True)
class PayerProfile:
    name: str
    weight: float          # share of claims
    realization_mean: float  # paid / billed
    realization_sd: float
    lag_mean: float        # days
    lag_sd: float
    denial_rate: float     # share fully denied (paid = 0)


# Rough archetypes — Medicare pays low & fast, commercial pays high & slow,
# Medicaid pays medium & slow, self-pay is messy.
PAYERS: list[PayerProfile] = [
    PayerProfile("Medicare",   0.20, 0.32, 0.06, 22, 8,  0.03),
    PayerProfile("Medicaid",   0.18, 0.38, 0.08, 48, 18, 0.05),
    PayerProfile("BlueCross",  0.22, 0.62, 0.10, 38, 14, 0.06),
    PayerProfile("Aetna",      0.12, 0.55, 0.11, 42, 16, 0.07),
    PayerProfile("UnitedHC",   0.13, 0.58, 0.12, 45, 18, 0.08),
    PayerProfile("Cigna",      0.08, 0.60, 0.10, 40, 15, 0.07),
    PayerProfile("SelfPay",    0.07, 0.45, 0.25, 75, 40, 0.20),
]

CLAIM_TYPES = [
    # (label, base_billed_amount, sd)
    ("PerDiem_Detox",    1800, 250),
    ("CaseRate_ShortStay", 8500, 1200),
    ("CaseRate_Residential", 22000, 4000),
    ("Ancillary",         350,  90),
]


def _pick(profiles: list[PayerProfile]) -> PayerProfile:
    weights = np.array([p.weight for p in profiles])
    weights = weights / weights.sum()
    return profiles[RNG.choice(len(profiles), p=weights)]


def generate_claims(
    n: int = 6000,
    start: date = date(2024, 2, 1),
    end: date = date(2026, 5, 30),
) -> pd.DataFrame:
    """Generate `n` synthetic Detox claims between `start` and `end`.

    The most recent claims will have `paid_date` / `paid_amount` = NaN — these
    are *censored* (still pending). The pipeline trains only on resolved claims
    but the censored ones are what we ultimately forecast against.
    """
    total_days = (end - start).days
    rows = []
    today = end  # treat `end` as the "as-of" date

    for i in range(n):
        # Submission date — uniform-ish, slightly more recent volume
        offset = int(RNG.beta(2.0, 1.3) * total_days)
        sub_date = start + timedelta(days=offset)

        payer = _pick(PAYERS)
        ctype, base, sd = CLAIM_TYPES[RNG.choice(len(CLAIM_TYPES))]
        billed = max(50.0, RNG.normal(base, sd))

        in_network = RNG.random() < 0.78

        # Lag & realization — payer-driven, with claim-type modifiers
        lag = max(3.0, RNG.normal(payer.lag_mean, payer.lag_sd))
        if not in_network:
            lag *= 1.25
        if ctype == "CaseRate_Residential":
            lag *= 1.15  # bigger claims drag

        if RNG.random() < payer.denial_rate:
            realization = 0.0
        else:
            realization = float(np.clip(
                RNG.normal(payer.realization_mean, payer.realization_sd),
                0.05, 1.0,
            ))
            if not in_network:
                realization *= 0.78

        paid_date = sub_date + timedelta(days=int(round(lag)))
        if paid_date > today:
            # Right-censored: still pending as of `today`
            paid_date_out = None
            paid_amount_out = None
        else:
            paid_date_out = paid_date
            paid_amount_out = round(billed * realization, 2)

        rows.append({
            "claim_id": f"DTX-{i:06d}",
            "facility": "Detox",
            "submission_date": sub_date,
            "payer": payer.name,
            "claim_type": ctype,
            "in_network": in_network,
            "billed_amount": round(billed, 2),
            "paid_date": paid_date_out,
            "paid_amount": paid_amount_out,
        })

    df = pd.DataFrame(rows).sort_values("submission_date").reset_index(drop=True)
    return df


def split_resolved_pending(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split into resolved (have paid_date) and pending (right-censored) frames."""
    resolved = df[df["paid_date"].notna()].copy()
    resolved["lag_days"] = (
        pd.to_datetime(resolved["paid_date"]) - pd.to_datetime(resolved["submission_date"])
    ).dt.days
    resolved["realization_rate"] = resolved["paid_amount"] / resolved["billed_amount"]
    pending = df[df["paid_date"].isna()].copy()
    return resolved, pending


if __name__ == "__main__":
    df = generate_claims()
    res, pen = split_resolved_pending(df)
    print(f"Generated {len(df)} claims | resolved={len(res)} pending={len(pen)}")
    print(df.head())
