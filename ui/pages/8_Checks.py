"""Full accuracy-check panel across all entities, cash flow and consolidation."""

from __future__ import annotations

import streamlit as st

from consol.persistence import period_repo
from consol.services.dashboard_service import collect_all_checks
from ui.bootstrap import get_conn

st.title("✅ Accuracy Checks")

conn = get_conn()
periods = period_repo.list_all(conn)
if not periods:
    st.warning("Upload data first.")
    st.stop()

period_by_label = {p.label: p for p in periods}
plabel = st.selectbox("Period", list(period_by_label.keys()), index=len(periods) - 1)
period = period_by_label[plabel]

checks = collect_all_checks(conn, period.year, period.month)
if checks.empty:
    st.info("No checks to run for this period.")
    st.stop()

errors = checks[(checks["severity"] == "error") & (~checks["passed"])]
warnings = checks[(checks["severity"] == "warning") & (~checks["passed"])]

cols = st.columns(3)
cols[0].metric("Checks run", len(checks))
cols[1].metric("Errors", len(errors))
cols[2].metric("Warnings", len(warnings))

if len(errors):
    st.error(f"{len(errors)} error(s) need attention.")
elif len(warnings):
    st.warning(f"{len(warnings)} warning(s).")
else:
    st.success("All checks passed.")

show_failed_only = st.checkbox("Show failed checks only", value=bool(len(errors) or len(warnings)))
view = checks[~checks["passed"]] if show_failed_only else checks

st.dataframe(
    view.sort_values(["passed", "severity", "scope"]),
    hide_index=True,
    use_container_width=True,
    column_config={
        "scope": "Scope",
        "check": "Check",
        "severity": "Severity",
        "passed": st.column_config.CheckboxColumn("Passed"),
        "detail": "Detail",
    },
)
