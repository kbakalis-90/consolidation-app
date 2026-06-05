"""Variance computations: actual vs one or more comparatives.

Comparatives are typically the prior month, the prior year (same month) and the
budget. Output is a wide table: the actual value followed, for each comparative,
by the comparative value, the absolute delta and the percentage delta.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _pct(delta: float, base: float) -> float:
    if base is None or pd.isna(base) or abs(base) < 1e-9:
        return np.nan
    return delta / abs(base) * 100.0


def build_variance(
    current: pd.DataFrame,
    comparatives: dict[str, pd.DataFrame],
    keys: list[str],
    value_col: str = "amount",
) -> pd.DataFrame:
    """Assemble a wide variance table.

    ``current`` and each comparative frame must contain ``keys`` and ``value_col``.
    Row order follows ``current``; rows only present in a comparative are appended.
    """
    base = current.copy()
    order_map = {
        tuple(row[k] for k in keys): i
        for i, (_, row) in enumerate(base.reset_index(drop=True).iterrows())
    }

    table = (
        base.groupby(keys, as_index=False)[value_col].sum().rename(columns={value_col: "Actual"})
    )
    cols_order = list(keys) + ["Actual"]

    for label, comp in comparatives.items():
        c = (
            comp.groupby(keys, as_index=False)[value_col].sum().rename(columns={value_col: label})
            if not comp.empty
            else pd.DataFrame(columns=list(keys) + [label])
        )
        table = table.merge(c, on=keys, how="outer")
        cols_order += [label, f"{label} Δ", f"{label} %"]

    for col in ["Actual", *comparatives.keys()]:
        table[col] = table[col].fillna(0.0)

    for label in comparatives:
        table[f"{label} Δ"] = table["Actual"] - table[label]
        table[f"{label} %"] = [
            _pct(d, b) for d, b in zip(table[f"{label} Δ"], table[label], strict=True)
        ]

    table["_o"] = [order_map.get(tuple(r[k] for k in keys), 10**6) for _, r in table.iterrows()]
    table = table.sort_values("_o").drop(columns="_o").reset_index(drop=True)
    return table[cols_order]
