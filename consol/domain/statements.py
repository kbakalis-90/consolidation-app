"""Build Balance Sheet and P&L from a mapped trial balance.

Input amounts are canonical (debit +, credit -). Output ``StatementResult``
objects carry presentation amounts (see :mod:`consol.domain.sign_conventions`).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from consol.domain.sign_conventions import (
    CAPTION_CURRENT_YEAR_RESULT,
    income_positive,
    natural_amount,
)
from consol.models.enums import StatementType
from consol.models.results import StatementResult

# Section labels used in the balance sheet presentation.
SECTION_ASSETS = "Assets"
SECTION_LIABILITIES = "Liabilities"
SECTION_EQUITY = "Equity"

_MAPPING_COLS = [
    "account_code",
    "statement",
    "caption",
    "caption_order",
    "normal_sign",
    "is_equity",
    "is_cash",
]


@dataclass
class StatementsBundle:
    """Everything produced from one entity/period's TB in one currency."""

    balance_sheet: StatementResult
    profit_and_loss: StatementResult
    net_income: float
    total_assets: float
    total_liabilities_equity: float
    unmapped: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def balances(self) -> bool:
        return abs(self.total_assets - self.total_liabilities_equity) < 0.01


def caption_attributes(mapping: pd.DataFrame) -> pd.DataFrame:
    """Per-caption cash-flow attributes derived from a mapping.

    Returns columns: caption, cf_category, wc_class, is_cash. Where a caption
    spans multiple accounts, the first non-null category/class wins and is_cash
    is set if any contributing account is cash.
    """
    cols = ["caption", "cf_category", "wc_class", "is_cash"]
    if mapping.empty:
        return pd.DataFrame(columns=cols)
    work = mapping.copy()
    for c in ("cf_category", "wc_class"):
        if c not in work.columns:
            work[c] = None
    if "is_cash" not in work.columns:
        work["is_cash"] = 0
    grouped = work.groupby("caption", as_index=False).agg(
        cf_category=("cf_category", "first"),
        wc_class=("wc_class", "first"),
        is_cash=("is_cash", "max"),
    )
    return grouped[cols]


def _bs_section(row: pd.Series) -> str:
    if str(row["normal_sign"]).lower() == "debit":
        return SECTION_ASSETS
    return SECTION_EQUITY if int(row.get("is_equity", 0)) == 1 else SECTION_LIABILITIES


def build_statements(tb: pd.DataFrame, mapping: pd.DataFrame, currency: str) -> StatementsBundle:
    """Construct the BS and P&L for one entity/period.

    Unmapped accounts are never dropped: they are returned in ``unmapped`` and
    excluded from the section totals so any resulting imbalance stays visible.
    """
    tb = tb[["account_code", "account_desc", "amount_local"]].copy()
    tb["account_code"] = tb["account_code"].astype(str).str.strip()
    map_cols = [c for c in _MAPPING_COLS if c in mapping.columns]
    merged = tb.merge(mapping[map_cols], on="account_code", how="left")

    unmapped = merged[merged["statement"].isna()][
        ["account_code", "account_desc", "amount_local"]
    ].reset_index(drop=True)
    mapped = merged[merged["statement"].notna()].copy()

    pl = mapped[mapped["statement"] == StatementType.PL.value].copy()
    bs = mapped[mapped["statement"] == StatementType.BS.value].copy()

    # Net income (income-positive): revenue (credit) less expenses (debit).
    net_income = float(income_positive(pl["amount_local"]).sum()) if not pl.empty else 0.0

    pl_result = _build_pl(pl, currency)
    bs_result, total_assets, total_le = _build_bs(bs, net_income, currency)

    return StatementsBundle(
        balance_sheet=bs_result,
        profit_and_loss=pl_result,
        net_income=net_income,
        total_assets=total_assets,
        total_liabilities_equity=total_le,
        unmapped=unmapped,
    )


def _build_pl(pl: pd.DataFrame, currency: str) -> StatementResult:
    if pl.empty:
        empty = pd.DataFrame(columns=["caption", "caption_order", "amount"])
        return StatementResult(StatementType.PL, currency, empty)
    pl = pl.copy()
    pl["amount"] = income_positive(pl["amount_local"])
    lines = (
        pl.groupby(["caption", "caption_order"], as_index=False)["amount"]
        .sum()
        .sort_values(["caption_order", "caption"])
        .reset_index(drop=True)
    )
    meta = {"net_income": float(lines["amount"].sum())}
    return StatementResult(StatementType.PL, currency, lines, meta=meta)


def _build_bs(
    bs: pd.DataFrame, net_income: float, currency: str
) -> tuple[StatementResult, float, float]:
    rows = []
    if not bs.empty:
        bs = bs.copy()
        bs["amount"] = natural_amount(bs["amount_local"], bs["normal_sign"])
        bs["section"] = bs.apply(_bs_section, axis=1)
        grouped = bs.groupby(["section", "caption", "caption_order"], as_index=False)[
            "amount"
        ].sum()
        rows.append(grouped)

    # Current-year result lands in equity so the balance sheet can balance.
    rows.append(
        pd.DataFrame(
            [
                {
                    "section": SECTION_EQUITY,
                    "caption": CAPTION_CURRENT_YEAR_RESULT,
                    "caption_order": 9000,
                    "amount": net_income,
                }
            ]
        )
    )

    lines = pd.concat(rows, ignore_index=True)
    _section_rank = {SECTION_ASSETS: 0, SECTION_LIABILITIES: 1, SECTION_EQUITY: 2}
    lines["_srank"] = lines["section"].map(_section_rank).fillna(9)
    lines = lines.sort_values(["_srank", "caption_order", "caption"]).drop(columns="_srank")
    lines = lines.reset_index(drop=True)

    total_assets = float(lines.loc[lines["section"] == SECTION_ASSETS, "amount"].sum())
    total_le = float(
        lines.loc[lines["section"].isin([SECTION_LIABILITIES, SECTION_EQUITY]), "amount"].sum()
    )
    result = StatementResult(
        StatementType.BS,
        currency,
        lines,
        meta={"total_assets": total_assets, "total_liabilities_equity": total_le},
    )
    return result, total_assets, total_le
