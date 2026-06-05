"""Render CashFlowResult objects."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from consol.models.results import CashFlowResult


def render_cashflow(cf: CashFlowResult, title: str) -> None:
    st.subheader(f"{title} ({cf.currency})")
    if cf.lines.empty:
        st.info("No cash flow lines.")
    else:
        for section in cf.lines["section"].drop_duplicates():
            sub = cf.lines[cf.lines["section"] == section]
            st.markdown(f"**{section}**")
            st.dataframe(
                sub[["line", "amount"]],
                hide_index=True,
                use_container_width=True,
                column_config={
                    "amount": st.column_config.NumberColumn(
                        f"Amount ({cf.currency})", format="%.2f"
                    )
                },
            )
            st.caption(f"Subtotal: {sub['amount'].sum():,.2f}")

    movement = cf.closing_cash - cf.opening_cash
    cols = st.columns(4)
    cols[0].metric("Net change", f"{cf.net_change:,.2f}")
    cols[1].metric("Opening cash", f"{cf.opening_cash:,.2f}")
    cols[2].metric("Closing cash", f"{cf.closing_cash:,.2f}")
    cols[3].metric("Cash movement", f"{movement:,.2f}", delta=f"{cf.net_change - movement:,.2f}")
    if abs(cf.net_change - movement) > 0.01:
        st.error("Cash flow does not reconcile to the movement in cash balances.")


def render_comparison(indirect: CashFlowResult, direct: CashFlowResult) -> None:
    """Side-by-side net-change comparison of the two methods."""
    df = pd.DataFrame(
        {
            "Method": ["Indirect", "Direct"],
            "Net change in cash": [indirect.net_change, direct.net_change],
        }
    )
    st.dataframe(df, hide_index=True, use_container_width=True)
    if abs(indirect.net_change - direct.net_change) > 0.01:
        st.warning("The two methods disagree on the net change in cash.")
