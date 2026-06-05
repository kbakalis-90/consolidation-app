"""Render StatementResult objects as formatted tables."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from consol.domain.statements import (
    SECTION_ASSETS,
    SECTION_EQUITY,
    SECTION_LIABILITIES,
    StatementsBundle,
)
from consol.models.results import StatementResult


def _fmt(df: pd.DataFrame, currency: str) -> None:
    st.dataframe(
        df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "amount": st.column_config.NumberColumn(f"Amount ({currency})", format="%.2f"),
        },
    )


def render_balance_sheet(result: StatementResult) -> None:
    st.subheader(f"Balance Sheet ({result.currency})")
    lines = result.lines
    if lines.empty:
        st.info("No balance sheet lines.")
        return
    for section, label in (
        (SECTION_ASSETS, "Assets"),
        (SECTION_LIABILITIES, "Liabilities"),
        (SECTION_EQUITY, "Equity"),
    ):
        sub = lines[lines["section"] == section]
        if sub.empty:
            continue
        st.markdown(f"**{label}**")
        _fmt(sub[["caption", "amount"]], result.currency)
        st.caption(f"Total {label}: {sub['amount'].sum():,.2f}")

    total_assets = result.meta.get("total_assets", 0.0)
    total_le = result.meta.get("total_liabilities_equity", 0.0)
    col1, col2 = st.columns(2)
    col1.metric("Total assets", f"{total_assets:,.2f}")
    col2.metric("Total liabilities + equity", f"{total_le:,.2f}")


def render_pl(result: StatementResult) -> None:
    st.subheader(f"Profit & Loss ({result.currency})")
    if result.lines.empty:
        st.info("No P&L lines.")
        return
    _fmt(result.lines[["caption", "amount"]], result.currency)
    st.metric("Net income", f"{result.total:,.2f}")


def render_bundle(bundle: StatementsBundle) -> None:
    col1, col2 = st.columns(2)
    with col1:
        render_balance_sheet(bundle.balance_sheet)
    with col2:
        render_pl(bundle.profit_and_loss)
    if not bundle.unmapped.empty:
        st.warning(
            f"{len(bundle.unmapped)} unmapped account(s) excluded from the statements "
            "(see below). These break the balance until mapped."
        )
        st.dataframe(bundle.unmapped, hide_index=True, use_container_width=True)
