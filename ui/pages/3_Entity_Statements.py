"""Entity statements page: per-entity Balance Sheet and P&L in local currency."""

from __future__ import annotations

import streamlit as st

from consol.persistence import entity_repo, period_repo
from consol.services.reporting_service import ReportingError, build_entity_report
from ui.bootstrap import get_conn
from ui.components.check_badge import render_check_summary
from ui.components.statement_table import render_bundle

st.title("📊 Entity Statements")

conn = get_conn()
entities = entity_repo.list_all(conn)
periods = period_repo.list_all(conn)
if not entities or not periods:
    st.warning("Upload at least one entity's trial balance on the Upload page first.")
    st.stop()

entity_by_label = {f"{e.code} — {e.name}": e for e in entities}
period_by_label = {p.label: p for p in periods}

cols = st.columns(2)
elabel = cols[0].selectbox("Entity", list(entity_by_label.keys()))
plabel = cols[1].selectbox("Period", list(period_by_label.keys()), index=len(periods) - 1)
entity = entity_by_label[elabel]
period = period_by_label[plabel]

try:
    report = build_entity_report(conn, entity.entity_id, period.year, period.month)
except ReportingError as exc:
    st.error(str(exc))
    st.stop()

st.caption(f"{report.entity.name} — {report.period_label} — {report.entity.local_currency}")
render_check_summary(report.checks)
render_bundle(report.bundle)
