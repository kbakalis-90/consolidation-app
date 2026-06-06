"""Consolidation page: translated group statements, eliminations, IC recon, CTA."""

from __future__ import annotations

import streamlit as st

from consol.persistence import period_repo
from consol.services.consolidation_service import ConsolidationError
from ui import cache
from ui.bootstrap import get_conn
from ui.components.check_badge import render_blocking_banner, render_check_summary
from ui.components.statement_table import render_balance_sheet, render_pl

st.title("🌍 Consolidation")

conn = get_conn()
periods = period_repo.list_all(conn)
if not periods:
    st.warning("Upload trial balances and FX rates first.")
    st.stop()

period_by_label = {p.label: p for p in periods}
plabel = st.selectbox("Period", list(period_by_label.keys()), index=len(periods) - 1)
period = period_by_label[plabel]

try:
    report = cache.build_consolidation(period.year, period.month, cache.data_version())
except ConsolidationError as exc:
    st.error(str(exc))
    st.stop()

st.caption(f"Group currency: {report.group_currency} — period {report.period_label}")
if report.missing_tb:
    st.warning(f"No trial balance for: {', '.join(report.missing_tb)} (excluded from group).")

render_check_summary(report.checks)
render_blocking_banner(report.checks)

if report.result is None:
    st.info("Nothing to consolidate yet — upload entity trial balances and FX rates.")
    st.stop()

col1, col2 = st.columns(2)
with col1:
    render_balance_sheet(report.result.balance_sheet)
with col2:
    render_pl(report.result.profit_and_loss)

st.divider()
st.subheader("Cumulative translation adjustment (CTA) by entity")
st.dataframe(report.result.cta_rollforward, hide_index=True, use_container_width=True)

with st.expander("Intercompany reconciliation"):
    if report.result.ic_reconciliation.empty:
        st.info("No intercompany balances for this period.")
    else:
        st.dataframe(report.result.ic_reconciliation, hide_index=True, use_container_width=True)

with st.expander("Elimination entries"):
    if report.result.eliminations.empty:
        st.info("No eliminations applied.")
    else:
        st.dataframe(report.result.eliminations, hide_index=True, use_container_width=True)

with st.expander("Per-entity translated balances"):
    st.dataframe(
        [
            {
                "Entity": te.entity.code,
                "Currency": te.entity.local_currency,
                "Assets": te.total_assets,
                "Liab+Equity": te.total_liabilities_equity,
                "Net income": te.net_income,
                "CTA": te.cta,
                "Closing": te.rates["closing"],
                "Average": te.rates["average"],
                "Historical": te.rates["historical"],
            }
            for te in report.translated
        ],
        hide_index=True,
        use_container_width=True,
    )
