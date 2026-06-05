"""Direct cash flow, built from uploaded gross cash receipts and payments."""

from __future__ import annotations

import pandas as pd

from consol.domain.cashflow_indirect import (
    SECTION_FINANCING,
    SECTION_INVESTING,
    SECTION_OPERATING,
)
from consol.models.results import CashFlowResult

_SECTION_BY_CF = {
    "operating": SECTION_OPERATING,
    "investing": SECTION_INVESTING,
    "financing": SECTION_FINANCING,
}
_RANK = {SECTION_OPERATING: 0, SECTION_INVESTING: 1, SECTION_FINANCING: 2}


def build_direct_cashflow(
    cash: pd.DataFrame,
    currency: str,
    opening_cash: float,
    closing_cash: float,
) -> CashFlowResult:
    """Build the direct statement from cash transactions.

    ``cash`` columns: cf_category, direct_line, flow_sign, amount_local.
    """
    work = cash.copy()
    work["amount"] = work.apply(
        lambda r: (
            float(r["amount_local"]) if r["flow_sign"] == "receipt" else -float(r["amount_local"])
        ),
        axis=1,
    )
    work["section"] = work["cf_category"].map(_SECTION_BY_CF).fillna(SECTION_OPERATING)
    lines = work.groupby(["section", "direct_line"], as_index=False)["amount"].sum()
    lines = lines.rename(columns={"direct_line": "line"})
    lines["_r"] = lines["section"].map(_RANK).fillna(9)
    lines = lines.sort_values(["_r", "line"]).drop(columns="_r").reset_index(drop=True)

    net_change = float(lines["amount"].sum()) if not lines.empty else 0.0
    return CashFlowResult(
        method="direct",
        currency=currency,
        lines=lines,
        net_change=net_change,
        opening_cash=opening_cash,
        closing_cash=closing_cash,
        meta={"cash_movement": closing_cash - opening_cash},
    )
