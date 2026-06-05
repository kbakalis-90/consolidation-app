"""Current-rate method translation (IAS 21) with a CTA balancing plug.

Balance sheet items translate at the closing rate, P&L at the average rate, and
non-result equity at a historical rate. The residual that makes the translated
balance sheet balance is booked to a Cumulative Translation Adjustment (CTA)
line within equity.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from consol.config import FX_DIRECTION_GROUP_PER_LOCAL
from consol.domain.sign_conventions import CAPTION_CURRENT_YEAR_RESULT
from consol.domain.statements import (
    SECTION_ASSETS,
    SECTION_EQUITY,
    SECTION_LIABILITIES,
    StatementsBundle,
)
from consol.models.entities import Entity
from consol.models.enums import StatementType
from consol.models.results import StatementResult

CAPTION_CTA = "Cumulative translation adjustment"
_CTA_ORDER = 9500


def convert(amount: float, rate: float, direction: str) -> float:
    """Convert a local-currency amount to the group currency."""
    if direction == FX_DIRECTION_GROUP_PER_LOCAL:
        return amount * rate
    return amount / rate


@dataclass
class TranslatedEntity:
    entity: Entity
    balance_sheet: StatementResult
    profit_and_loss: StatementResult
    net_income: float
    total_assets: float
    total_liabilities_equity: float
    cta: float
    rates: dict[str, float]

    @property
    def balances(self) -> bool:
        return abs(self.total_assets - self.total_liabilities_equity) < 0.01


def _bs_rate(
    section: str, caption: str, closing: float, average: float, historical: float
) -> float:
    if section == SECTION_EQUITY:
        return average if caption == CAPTION_CURRENT_YEAR_RESULT else historical
    # Assets and liabilities translate at the closing rate.
    return closing


def translate_bundle(
    bundle: StatementsBundle,
    entity: Entity,
    closing_rate: float,
    average_rate: float,
    group_currency: str,
    direction: str = FX_DIRECTION_GROUP_PER_LOCAL,
    equity_historical_rate: float | None = None,
) -> TranslatedEntity:
    """Translate one entity's local statements to the group currency."""
    historical = equity_historical_rate if equity_historical_rate is not None else closing_rate

    # --- Balance sheet ---
    bs = bundle.balance_sheet.lines.copy()
    if bs.empty:
        bs = pd.DataFrame(columns=["section", "caption", "caption_order", "amount"])
    bs["rate"] = bs.apply(
        lambda r: _bs_rate(r["section"], r["caption"], closing_rate, average_rate, historical),
        axis=1,
    )
    bs["amount"] = [
        convert(a, rate, direction) for a, rate in zip(bs["amount"], bs["rate"], strict=True)
    ]
    bs = bs.drop(columns="rate")

    total_assets = float(bs.loc[bs["section"] == SECTION_ASSETS, "amount"].sum())
    total_le_pre = float(
        bs.loc[bs["section"].isin([SECTION_LIABILITIES, SECTION_EQUITY]), "amount"].sum()
    )
    cta = total_assets - total_le_pre

    cta_row = pd.DataFrame(
        [
            {
                "section": SECTION_EQUITY,
                "caption": CAPTION_CTA,
                "caption_order": _CTA_ORDER,
                "amount": cta,
            }
        ]
    )
    bs = pd.concat([bs, cta_row], ignore_index=True)
    total_le = total_le_pre + cta

    bs_result = StatementResult(
        StatementType.BS,
        group_currency,
        bs,
        meta={"total_assets": total_assets, "total_liabilities_equity": total_le, "cta": cta},
    )

    # --- P&L (all at average) ---
    pl = bundle.profit_and_loss.lines.copy()
    if not pl.empty:
        pl["amount"] = [convert(a, average_rate, direction) for a in pl["amount"]]
    net_income = float(pl["amount"].sum()) if not pl.empty else 0.0
    pl_result = StatementResult(
        StatementType.PL, group_currency, pl, meta={"net_income": net_income}
    )

    return TranslatedEntity(
        entity=entity,
        balance_sheet=bs_result,
        profit_and_loss=pl_result,
        net_income=net_income,
        total_assets=total_assets,
        total_liabilities_equity=total_le,
        cta=cta,
        rates={"closing": closing_rate, "average": average_rate, "historical": historical},
    )
