"""Render a wide variance table from consol.domain.variance."""

from __future__ import annotations

import pandas as pd
import streamlit as st


def render_variance(table: pd.DataFrame, title: str, currency: str) -> None:
    st.subheader(f"{title} ({currency})")
    if table.empty:
        st.info("No data.")
        return

    fmt: dict[str, object] = {}
    for col in table.columns:
        if col.endswith("%"):
            fmt[col] = st.column_config.NumberColumn(col, format="%.1f%%")
        elif table[col].dtype.kind in "fi":
            fmt[col] = st.column_config.NumberColumn(col, format="%.2f")
    st.dataframe(table, hide_index=True, use_container_width=True, column_config=fmt)
