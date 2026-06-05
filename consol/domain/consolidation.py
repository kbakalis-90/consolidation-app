"""Consolidate translated entities: aggregate, eliminate intercompany, reconcile.

Intercompany elimination removes the *matched* portion of each pair's balances
(min of the two sides), which keeps the consolidated balance sheet in balance and
net income unchanged. Any unmatched difference is reported in the reconciliation
table rather than silently distorting the statements.
"""

from __future__ import annotations

import pandas as pd

from consol.config import FX_DIRECTION_GROUP_PER_LOCAL
from consol.domain.statements import SECTION_ASSETS, SECTION_EQUITY, SECTION_LIABILITIES
from consol.domain.translation import TranslatedEntity, convert
from consol.models.enums import StatementType
from consol.models.results import ConsolidationResult, StatementResult

_SECTION_RANK = {SECTION_ASSETS: 0, SECTION_LIABILITIES: 1, SECTION_EQUITY: 2}
_BS_TYPES = ("receivable", "payable")


def _ic_amount_group(
    row: pd.Series, fx_rates: dict[str, tuple[float, float]], direction: str
) -> float:
    closing, average = fx_rates[row["entity_ccy"]]
    rate = closing if row["ic_type"] in _BS_TYPES else average
    return convert(float(row["amount_local"]), rate, direction)


def _pair_key(a: str, b: str) -> str:
    return "|".join(sorted([a, b]))


def _build_eliminations(
    ic: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (elimination_deltas, reconciliation) given IC rows with amount_group.

    ``elimination_deltas`` columns: statement, section, caption, amount (signed
    deltas to apply to the consolidated presentation lines).
    """
    delta_rows: list[dict] = []
    recon_rows: list[dict] = []

    for pair, grp in ic.groupby("pair"):
        recv = grp[grp["ic_type"] == "receivable"]
        pay = grp[grp["ic_type"] == "payable"]
        inc = grp[grp["ic_type"] == "income"]
        exp = grp[grp["ic_type"] == "expense"]

        recv_total = float(recv["amount_group"].sum())
        pay_total = float(pay["amount_group"].sum())
        inc_total = float(inc["amount_group"].sum())
        exp_total = float(exp["amount_group"].sum())

        matched_bs = min(recv_total, pay_total)
        matched_pl = min(inc_total, exp_total)

        # Balance-sheet eliminations: reduce receivable assets and payable
        # liabilities by the matched amount, distributed across their captions.
        for _, r in recv.iterrows():
            if recv_total > 0:
                delta_rows.append(
                    {
                        "statement": StatementType.BS.value,
                        "section": SECTION_ASSETS,
                        "caption": r["caption"],
                        "amount": -matched_bs * r["amount_group"] / recv_total,
                    }
                )
        for _, r in pay.iterrows():
            if pay_total > 0:
                delta_rows.append(
                    {
                        "statement": StatementType.BS.value,
                        "section": SECTION_LIABILITIES,
                        "caption": r["caption"],
                        "amount": -matched_bs * r["amount_group"] / pay_total,
                    }
                )
        # P&L eliminations: reduce IC revenue and the matching IC expense.
        # Expenses are stored income-positive (negative), so removing expense adds.
        for _, r in inc.iterrows():
            if inc_total > 0:
                delta_rows.append(
                    {
                        "statement": StatementType.PL.value,
                        "section": None,
                        "caption": r["caption"],
                        "amount": -matched_pl * r["amount_group"] / inc_total,
                    }
                )
        for _, r in exp.iterrows():
            if exp_total > 0:
                delta_rows.append(
                    {
                        "statement": StatementType.PL.value,
                        "section": None,
                        "caption": r["caption"],
                        "amount": matched_pl * r["amount_group"] / exp_total,
                    }
                )

        recon_rows.append(
            {
                "pair": pair,
                "ic_receivable": recv_total,
                "ic_payable": pay_total,
                "bs_difference": recv_total - pay_total,
                "ic_income": inc_total,
                "ic_expense": exp_total,
                "pnl_difference": inc_total - exp_total,
            }
        )

    deltas = pd.DataFrame(delta_rows, columns=["statement", "section", "caption", "amount"])
    recon = pd.DataFrame(
        recon_rows,
        columns=[
            "pair",
            "ic_receivable",
            "ic_payable",
            "bs_difference",
            "ic_income",
            "ic_expense",
            "pnl_difference",
        ],
    )
    return deltas, recon


def _aggregate_bs(entities: list[TranslatedEntity], deltas: pd.DataFrame) -> pd.DataFrame:
    frames = [
        te.balance_sheet.lines[["section", "caption", "caption_order", "amount"]] for te in entities
    ]
    combined = (
        pd.concat(frames, ignore_index=True)
        if frames
        else pd.DataFrame(columns=["section", "caption", "caption_order", "amount"])
    )
    bs_deltas = deltas[deltas["statement"] == StatementType.BS.value]
    if not bs_deltas.empty:
        add = bs_deltas[["section", "caption", "amount"]].copy()
        add["caption_order"] = pd.NA
        combined = pd.concat([combined, add], ignore_index=True)
    agg = combined.groupby(["section", "caption"], as_index=False).agg(
        amount=("amount", "sum"), caption_order=("caption_order", "min")
    )
    agg["caption_order"] = agg["caption_order"].fillna(9999).astype(int)
    agg["_srank"] = agg["section"].map(_SECTION_RANK).fillna(9)
    return agg.sort_values(["_srank", "caption_order", "caption"]).drop(columns="_srank")


def _aggregate_pl(entities: list[TranslatedEntity], deltas: pd.DataFrame) -> pd.DataFrame:
    frames = [te.profit_and_loss.lines[["caption", "caption_order", "amount"]] for te in entities]
    combined = (
        pd.concat(frames, ignore_index=True)
        if frames
        else pd.DataFrame(columns=["caption", "caption_order", "amount"])
    )
    pl_deltas = deltas[deltas["statement"] == StatementType.PL.value]
    if not pl_deltas.empty:
        add = pl_deltas[["caption", "amount"]].copy()
        add["caption_order"] = pd.NA
        combined = pd.concat([combined, add], ignore_index=True)
    agg = combined.groupby("caption", as_index=False).agg(
        amount=("amount", "sum"), caption_order=("caption_order", "min")
    )
    agg["caption_order"] = agg["caption_order"].fillna(9999).astype(int)
    return agg.sort_values(["caption_order", "caption"]).reset_index(drop=True)


def consolidate(
    entities: list[TranslatedEntity],
    ic: pd.DataFrame,
    fx_rates: dict[str, tuple[float, float]],
    group_currency: str,
    direction: str = FX_DIRECTION_GROUP_PER_LOCAL,
) -> ConsolidationResult:
    """Build the consolidated BS and P&L from translated entities and IC balances."""
    if ic is not None and not ic.empty:
        ic = ic.copy()
        ic["amount_group"] = ic.apply(lambda r: _ic_amount_group(r, fx_rates, direction), axis=1)
        ic["pair"] = ic.apply(lambda r: _pair_key(r["entity_code"], r["counterparty_code"]), axis=1)
        deltas, recon = _build_eliminations(ic)
    else:
        deltas = pd.DataFrame(columns=["statement", "section", "caption", "amount"])
        recon = pd.DataFrame(
            columns=[
                "pair",
                "ic_receivable",
                "ic_payable",
                "bs_difference",
                "ic_income",
                "ic_expense",
                "pnl_difference",
            ]
        )

    bs_agg = _aggregate_bs(entities, deltas)
    pl_agg = _aggregate_pl(entities, deltas)

    total_assets = float(bs_agg.loc[bs_agg["section"] == SECTION_ASSETS, "amount"].sum())
    total_le = float(
        bs_agg.loc[bs_agg["section"].isin([SECTION_LIABILITIES, SECTION_EQUITY]), "amount"].sum()
    )
    bs_result = StatementResult(
        StatementType.BS,
        group_currency,
        bs_agg.reset_index(drop=True),
        meta={"total_assets": total_assets, "total_liabilities_equity": total_le},
    )
    pl_result = StatementResult(
        StatementType.PL,
        group_currency,
        pl_agg,
        meta={"net_income": float(pl_agg["amount"].sum())},
    )

    cta_rollforward = pd.DataFrame(
        [{"entity": te.entity.code, "closing_cta": te.cta} for te in entities]
    )

    return ConsolidationResult(
        balance_sheet=bs_result,
        profit_and_loss=pl_result,
        eliminations=deltas,
        ic_reconciliation=recon,
        cta_rollforward=cta_rollforward,
        meta={"total_assets": total_assets, "total_liabilities_equity": total_le},
    )
