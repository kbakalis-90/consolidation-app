"""Comparatives page: actual vs prior month / prior year / budget."""

from __future__ import annotations

import streamlit as st

from consol.persistence import entity_repo, period_repo
from consol.services.comparatives_service import ComparativesError
from ui import cache
from ui.bootstrap import get_conn
from ui.components.check_badge import render_blocking_banner, render_check_summary
from ui.components.variance_table import render_variance

st.title("📈 Comparatives & Variance")

conn = get_conn()
entities = entity_repo.list_all(conn)
periods = period_repo.list_all(conn)
if not periods:
    st.warning("Upload trial balances first.")
    st.stop()

period_by_label = {p.label: p for p in periods}
scope = st.radio("Scope", ["Single entity", "Consolidated (group)"], horizontal=True)
plabel = st.selectbox("Period", list(period_by_label.keys()), index=len(periods) - 1)
period = period_by_label[plabel]

try:
    if scope == "Single entity":
        if not entities:
            st.warning("Add an entity first.")
            st.stop()
        entity_by_label = {f"{e.code} — {e.name}": e for e in entities}
        elabel = st.selectbox("Entity", list(entity_by_label.keys()))
        entity = entity_by_label[elabel]
        report = cache.build_entity_comparatives(
            entity.entity_id, period.year, period.month, cache.data_version()
        )
    else:
        report = cache.build_consolidated_comparatives(
            period.year, period.month, cache.data_version()
        )
except ComparativesError as exc:
    st.error(str(exc))
    st.stop()

st.caption(f"{report.title} — {report.period_label} — {report.currency}")
avail = ", ".join(f"{k}: {'✓' if v else '—'}" for k, v in report.available.items())
st.caption(f"Comparatives available — {avail}")
render_check_summary(report.checks)
render_blocking_banner(report.checks)

render_variance(report.bs_variance, "Balance Sheet", report.currency)
render_variance(report.pl_variance, "Profit & Loss", report.currency)
