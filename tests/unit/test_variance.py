import numpy as np
import pandas as pd

from consol.domain.variance import build_variance


def _bs(cash, ar):
    return pd.DataFrame(
        {
            "section": ["Assets", "Assets"],
            "caption": ["Cash", "Trade receivables"],
            "amount": [cash, ar],
        }
    )


def test_variance_basic_deltas_and_pct():
    current = _bs(100.0, 50.0)
    comps = {"Prior month": _bs(80.0, 40.0)}
    table = build_variance(current, comps, keys=["section", "caption"])

    row = table[table["caption"] == "Cash"].iloc[0]
    assert row["Actual"] == 100.0
    assert row["Prior month"] == 80.0
    assert row["Prior month Δ"] == 20.0
    assert round(row["Prior month %"], 1) == 25.0


def test_variance_multiple_comparatives_column_order():
    current = _bs(100.0, 50.0)
    comps = {"Prior month": _bs(80.0, 40.0), "Budget": _bs(120.0, 45.0)}
    table = build_variance(current, comps, keys=["section", "caption"])
    assert list(table.columns) == [
        "section",
        "caption",
        "Actual",
        "Prior month",
        "Prior month Δ",
        "Prior month %",
        "Budget",
        "Budget Δ",
        "Budget %",
    ]


def test_variance_pct_nan_when_base_zero():
    current = _bs(100.0, 50.0)
    comps = {"Budget": pd.DataFrame({"section": ["Assets"], "caption": ["Cash"], "amount": [0.0]})}
    table = build_variance(current, comps, keys=["section", "caption"])
    cash = table[table["caption"] == "Cash"].iloc[0]
    assert cash["Budget Δ"] == 100.0
    assert np.isnan(cash["Budget %"])


def test_variance_caption_only_in_comparative_has_zero_actual():
    current = _bs(100.0, 50.0)
    comps = {
        "Prior month": pd.DataFrame(
            {"section": ["Assets"], "caption": ["Prepayments"], "amount": [30.0]}
        )
    }
    table = build_variance(current, comps, keys=["section", "caption"])
    extra = table[table["caption"] == "Prepayments"].iloc[0]
    assert extra["Actual"] == 0.0
    assert extra["Prior month"] == 30.0
    assert extra["Prior month Δ"] == -30.0
