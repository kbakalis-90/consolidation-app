"""Render check results as a compact panel."""

from __future__ import annotations

import streamlit as st

from consol.checks.registry import CheckSummary


def render_check_summary(summary: CheckSummary) -> None:
    errors = summary.errors
    warnings = summary.warnings
    if not summary.results:
        return

    if errors:
        st.error(f"{len(errors)} check(s) failed.")
    elif warnings:
        st.warning(f"All critical checks passed, {len(warnings)} warning(s).")
    else:
        st.success("All checks passed.")

    with st.expander("Check details", expanded=bool(errors)):
        for r in summary.results:
            icon = "✅" if r.passed else ("⚠️" if r.severity.value == "warning" else "❌")
            st.markdown(f"{icon} **{r.description}** — {r.detail}")
            if r.rows is not None and not r.passed:
                st.dataframe(r.rows, hide_index=True, use_container_width=True)
