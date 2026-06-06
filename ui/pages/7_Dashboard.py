"""KPI dashboard for an entity or the consolidated group."""

from __future__ import annotations

import numpy as np
import streamlit as st

from consol.domain.kpis import FMT_CURRENCY, FMT_PERCENT, FMT_RATIO
from consol.persistence import entity_repo, period_repo
from consol.services.dashboard_service import DashboardError
from ui import cache
from ui.bootstrap import get_conn
from ui.components.check_badge import render_blocking_banner, render_check_summary

st.title("📋 Dashboard")

conn = get_conn()
periods = period_repo.list_all(conn)
entities = entity_repo.list_all(conn)
if not periods:
    st.warning("Upload trial balances first.")
    st.stop()

period_by_label = {p.label: p for p in periods}
scope_label = st.radio("Scope", ["Single entity", "Consolidated (group)"], horizontal=True)
plabel = st.selectbox("Period", list(period_by_label.keys()), index=len(periods) - 1)
period = period_by_label[plabel]

entity_id = None
scope = "entity" if scope_label == "Single entity" else "group"
if scope == "entity":
    if not entities:
        st.warning("Add an entity first.")
        st.stop()
    entity_by_label = {f"{e.code} — {e.name}": e for e in entities}
    elabel = st.selectbox("Entity", list(entity_by_label.keys()))
    entity_id = entity_by_label[elabel].entity_id

try:
    report = cache.build_dashboard(
        scope, period.year, period.month, entity_id, cache.data_version()
    )
except DashboardError as exc:
    st.error(str(exc))
    st.stop()


def _fmt(value: float, fmt: str, currency: str) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "n/a"
    if fmt == FMT_PERCENT:
        return f"{value:,.1f}%"
    if fmt == FMT_RATIO:
        return f"{value:,.2f}x"
    if fmt == FMT_CURRENCY:
        return f"{value:,.0f} {currency}"
    return f"{value:,.2f}"


st.caption(f"{report.title} — {report.period_label} — {report.currency}")
render_check_summary(report.checks)
render_blocking_banner(report.checks)

if report.revenue_growth is not None and not np.isnan(report.revenue_growth):
    st.metric("Revenue growth vs prior month", f"{report.revenue_growth:,.1f}%")

groups: dict[str, list] = {}
for k in report.kpis:
    groups.setdefault(k.group, []).append(k)

for group_name, items in groups.items():
    st.subheader(group_name)
    cols = st.columns(len(items))
    for col, kpi in zip(cols, items, strict=False):
        col.metric(kpi.name, _fmt(kpi.value, kpi.fmt, report.currency))
