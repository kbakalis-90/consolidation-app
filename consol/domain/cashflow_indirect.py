"""Indirect cash flow, derived from balance-sheet movements.

Every non-cash balance-sheet movement is converted into a cash effect and
bucketed into operating/investing/financing. Because all non-cash movements are
included exactly once, the total equals the actual change in cash (the
accounting identity Assets = Liabilities + Equity guarantees it).

The operating section starts from the movement in the result-for-the-period
line rather than a separately computed net income, which keeps the statement
reconciling across any pair of periods.
"""

from __future__ import annotations

import pandas as pd

from consol.domain.sign_conventions import CAPTION_CURRENT_YEAR_RESULT
from consol.domain.statements import SECTION_ASSETS
from consol.domain.translation import CAPTION_CTA
from consol.models.results import CashFlowResult, StatementResult

SECTION_OPERATING = "Operating activities"
SECTION_INVESTING = "Investing activities"
SECTION_FINANCING = "Financing activities"
# Emitted only on the *consolidated* path (see cashflow_service), where translated
# entity flows are summed and the residual FX impact is booked as its own line.
# build_indirect_cashflow operates on LOCAL bundles and never produces it, but
# _order_sections must still rank it for the consolidated statement.
SECTION_FX = "Effect of exchange rate changes on cash"

_WC_LABELS = {
    "AR": "Change in trade receivables",
    "AP": "Change in trade payables",
    "inventory": "Change in inventory",
    "other_wc": "Change in other working capital",
}


def _enrich(lines: pd.DataFrame, attrs: pd.DataFrame) -> pd.DataFrame:
    out = lines.merge(attrs, on="caption", how="left")
    out["is_cash"] = out["is_cash"].fillna(0).astype(int)
    return out


def _classify(row: pd.Series) -> tuple[str, str] | None:
    """Return (section, line label) for a movement, or None to skip."""
    caption = row["caption"]
    if int(row.get("is_cash", 0)) == 1 or caption == CAPTION_CTA:
        return None
    if caption == CAPTION_CURRENT_YEAR_RESULT:
        return SECTION_OPERATING, "Result for the period"
    cf = row.get("cf_category")
    if cf == "investing":
        return SECTION_INVESTING, f"Change in {caption}"
    if cf == "financing":
        return SECTION_FINANCING, f"Change in {caption}"
    wc = row.get("wc_class")
    if isinstance(wc, str) and wc in _WC_LABELS:
        return SECTION_OPERATING, _WC_LABELS[wc]
    if row.get("section") == "Equity":
        return SECTION_FINANCING, f"Change in {caption}"
    return SECTION_OPERATING, f"Change in {caption}"


class CtaInIndirectCashflowError(ValueError):
    """Raised when a translated (CTA-bearing) bundle is fed to the LOCAL builder.

    ``build_indirect_cashflow`` relies on the identity ΔAssets = ΔLiabilities +
    ΔEquity to guarantee the non-cash movements sum to the cash movement. That
    identity only holds for LOCAL bundles. A translated bundle carries a CTA plug
    in equity that has no cash counterpart, so reconciliation would silently
    fail. The consolidated FX effect is handled separately (see cashflow_service).
    """


def _assert_no_cta(bs: StatementResult, label: str) -> None:
    lines = bs.lines
    if not lines.empty and (lines["caption"] == CAPTION_CTA).any():
        raise CtaInIndirectCashflowError(
            f"{label} balance sheet carries a '{CAPTION_CTA}' line; the indirect "
            "cash flow builder only accepts LOCAL (untranslated) bundles. Translate "
            "the resulting cash flows and add the FX effect separately instead."
        )


def build_indirect_cashflow(
    current_bs: StatementResult,
    prior_bs: StatementResult,
    caption_attrs: pd.DataFrame,
    currency: str,
) -> CashFlowResult:
    _assert_no_cta(current_bs, "Current")
    _assert_no_cta(prior_bs, "Prior")
    cur = current_bs.lines[["section", "caption", "amount"]].rename(columns={"amount": "cur"})
    pri = prior_bs.lines[["section", "caption", "amount"]].rename(columns={"amount": "pri"})

    merged = cur.merge(pri, on=["section", "caption"], how="outer")
    merged["cur"] = merged["cur"].fillna(0.0)
    merged["pri"] = merged["pri"].fillna(0.0)
    merged["delta"] = merged["cur"] - merged["pri"]
    merged = _enrich(merged, caption_attrs)

    rows = []
    opening_cash = 0.0
    closing_cash = 0.0
    for _, row in merged.iterrows():
        if int(row.get("is_cash", 0)) == 1:
            opening_cash += float(row["pri"])
            closing_cash += float(row["cur"])
            continue
        classified = _classify(row)
        if classified is None:
            continue
        section, line = classified
        # Cash effect: an asset increase uses cash; a liability/equity increase provides it.
        cash_impact = -row["delta"] if row["section"] == SECTION_ASSETS else row["delta"]
        rows.append({"section": section, "line": line, "amount": float(cash_impact)})

    lines = pd.DataFrame(rows, columns=["section", "line", "amount"])
    if not lines.empty:
        lines = lines.groupby(["section", "line"], as_index=False)["amount"].sum()
        lines = _order_sections(lines)
    net_change = float(lines["amount"].sum()) if not lines.empty else 0.0

    return CashFlowResult(
        method="indirect",
        currency=currency,
        lines=lines,
        net_change=net_change,
        opening_cash=opening_cash,
        closing_cash=closing_cash,
        meta={"cash_movement": closing_cash - opening_cash},
    )


def _order_sections(lines: pd.DataFrame) -> pd.DataFrame:
    rank = {SECTION_OPERATING: 0, SECTION_INVESTING: 1, SECTION_FINANCING: 2, SECTION_FX: 3}
    lines = lines.copy()
    lines["_r"] = lines["section"].map(rank).fillna(9)
    # Keep the result line first within operating.
    lines["_l"] = (lines["line"] != "Result for the period").astype(int)
    return lines.sort_values(["_r", "_l", "line"]).drop(columns=["_r", "_l"]).reset_index(drop=True)
