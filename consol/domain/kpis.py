"""KPI derivations from built statements. Pure functions over DataFrames."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from consol.domain.cashflow_indirect import SECTION_OPERATING
from consol.domain.statements import SECTION_ASSETS, SECTION_EQUITY, SECTION_LIABILITIES
from consol.models.results import CashFlowResult, StatementResult

# KPI value formats, used by the UI to render appropriately.
FMT_CURRENCY = "currency"
FMT_PERCENT = "percent"
FMT_RATIO = "ratio"


@dataclass
class KPI:
    name: str
    value: float
    fmt: str
    group: str  # "Profitability" | "Financial position" | "Liquidity" | "Cash flow"


def _safe_div(num: float, den: float) -> float:
    return num / den if den not in (0, None) and abs(den) > 1e-9 else np.nan


def _section_total(bs: StatementResult, section: str) -> float:
    return float(bs.lines.loc[bs.lines["section"] == section, "amount"].sum())


def _cash_and_working_capital(bs: StatementResult, attrs: pd.DataFrame) -> tuple[float, float]:
    if attrs is None or attrs.empty:
        return np.nan, np.nan
    merged = bs.lines.merge(attrs, on="caption", how="left")
    cash = float(merged.loc[merged["is_cash"].fillna(0).astype(int) == 1, "amount"].sum())
    ar = float(merged.loc[merged["wc_class"] == "AR", "amount"].sum())
    inv = float(merged.loc[merged["wc_class"] == "inventory", "amount"].sum())
    ap = float(merged.loc[merged["wc_class"] == "AP", "amount"].sum())
    working_capital = ar + inv - ap
    return cash, working_capital


def compute_kpis(
    bs: StatementResult,
    pl: StatementResult,
    attrs: pd.DataFrame | None = None,
    cashflow: CashFlowResult | None = None,
) -> list[KPI]:
    revenue = (
        float(pl.lines.loc[pl.lines["amount"] > 0, "amount"].sum()) if not pl.lines.empty else 0.0
    )
    expenses = (
        float(-pl.lines.loc[pl.lines["amount"] < 0, "amount"].sum()) if not pl.lines.empty else 0.0
    )
    net_income = pl.total

    total_assets = _section_total(bs, SECTION_ASSETS)
    total_liabilities = _section_total(bs, SECTION_LIABILITIES)
    total_equity = _section_total(bs, SECTION_EQUITY)
    cash, working_capital = _cash_and_working_capital(bs, attrs)

    kpis = [
        KPI("Revenue", revenue, FMT_CURRENCY, "Profitability"),
        KPI("Operating expenses", expenses, FMT_CURRENCY, "Profitability"),
        KPI("Net income", net_income, FMT_CURRENCY, "Profitability"),
        KPI("Net margin", _safe_div(net_income, revenue) * 100.0, FMT_PERCENT, "Profitability"),
        KPI("Total assets", total_assets, FMT_CURRENCY, "Financial position"),
        KPI("Total liabilities", total_liabilities, FMT_CURRENCY, "Financial position"),
        KPI("Total equity", total_equity, FMT_CURRENCY, "Financial position"),
        KPI(
            "Equity ratio",
            _safe_div(total_equity, total_assets) * 100.0,
            FMT_PERCENT,
            "Financial position",
        ),
        KPI(
            "Debt to equity",
            _safe_div(total_liabilities, total_equity),
            FMT_RATIO,
            "Financial position",
        ),
        KPI("Cash & equivalents", cash, FMT_CURRENCY, "Liquidity"),
        KPI("Working capital", working_capital, FMT_CURRENCY, "Liquidity"),
    ]
    if cashflow is not None:
        kpis.append(
            KPI(
                "Operating cash flow",
                cashflow.section_total(SECTION_OPERATING),
                FMT_CURRENCY,
                "Cash flow",
            )
        )
        kpis.append(KPI("Net change in cash", cashflow.net_change, FMT_CURRENCY, "Cash flow"))
    return kpis


def revenue_growth(current_pl: StatementResult, prior_pl: StatementResult) -> float:
    """Period-on-period revenue growth percentage."""
    cur = float(current_pl.lines.loc[current_pl.lines["amount"] > 0, "amount"].sum())
    pri = float(prior_pl.lines.loc[prior_pl.lines["amount"] > 0, "amount"].sum())
    return _safe_div(cur - pri, pri) * 100.0
