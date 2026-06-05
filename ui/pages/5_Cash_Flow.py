"""Cash flow page: per-entity indirect & direct methods, plus consolidated."""

from __future__ import annotations

import streamlit as st

from consol.persistence import entity_repo, period_repo
from consol.services.cashflow_service import (
    CashflowError,
    build_consolidated_cashflow,
    build_entity_cashflow,
)
from ui.bootstrap import get_conn
from ui.components.cashflow_table import render_cashflow, render_comparison
from ui.components.check_badge import render_check_summary

st.title("💧 Cash Flow")

conn = get_conn()
entities = entity_repo.list_all(conn)
periods = period_repo.list_all(conn)
if not entities or not periods:
    st.warning("Upload trial balances first (the indirect method also needs a prior period).")
    st.stop()

period_by_label = {p.label: p for p in periods}
scope = st.radio("Scope", ["Single entity", "Consolidated (group)"], horizontal=True)
plabel = st.selectbox("Period", list(period_by_label.keys()), index=len(periods) - 1)
period = period_by_label[plabel]

if scope == "Single entity":
    entity_by_label = {f"{e.code} — {e.name}": e for e in entities}
    elabel = st.selectbox("Entity", list(entity_by_label.keys()))
    entity = entity_by_label[elabel]
    try:
        report = build_entity_cashflow(conn, entity.entity_id, period.year, period.month)
    except CashflowError as exc:
        st.error(str(exc))
        st.stop()

    st.caption(f"{report.entity.name} — {report.period_label} — {report.currency}")
    render_check_summary(report.checks)

    if not report.has_prior:
        st.info("No prior period found — the indirect method needs an opening balance sheet.")

    if report.indirect is not None and report.direct is not None:
        render_comparison(report.indirect, report.direct)

    col1, col2 = st.columns(2)
    with col1:
        if report.indirect is not None:
            render_cashflow(report.indirect, "Indirect method")
        else:
            st.info("Indirect method unavailable (no prior period).")
    with col2:
        if report.direct is not None:
            render_cashflow(report.direct, "Direct method")
        else:
            st.info("No cash-transaction data uploaded for the direct method.")
else:
    try:
        report = build_consolidated_cashflow(conn, period.year, period.month)
    except CashflowError as exc:
        st.error(str(exc))
        st.stop()
    st.caption(f"Group currency: {report.group_currency} — {report.period_label}")
    if report.skipped:
        st.warning(f"Excluded (missing current or prior TB): {', '.join(report.skipped)}.")
    render_check_summary(report.checks)
    if report.indirect is not None:
        render_cashflow(report.indirect, "Consolidated indirect method")
    else:
        st.info("Consolidated cash flow needs at least one entity with current and prior data.")
