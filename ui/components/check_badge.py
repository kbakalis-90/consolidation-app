"""Render check results as a compact panel."""

from __future__ import annotations

import streamlit as st

from consol.checks.registry import CheckSummary


def blocking_banner_lines(summary: CheckSummary) -> list[str]:
    """Pure logic: the bullet lines for a blocking banner.

    Returns one ``"description — detail"`` (or just ``description``) string per
    failed ERROR check, or an empty list when there are no blocking errors. The
    empty list is the signal that no banner should be rendered.
    """
    if not summary.has_blocking_errors:
        return []
    lines = []
    for r in summary.errors:
        lines.append(f"{r.description} — {r.detail}" if r.detail else r.description)
    return lines


def render_blocking_banner(summary: CheckSummary) -> None:
    """Render an unmissable error banner when checks have blocking errors.

    No-op when there are no blocking errors. Call this immediately before
    rendering financial figures so the user is warned the figures may be
    unreliable (figures are still shown — we warn, we do not stop).
    """
    lines = blocking_banner_lines(summary)
    if not lines:
        return
    bullets = "\n".join(f"- {line}" for line in lines)
    st.error(
        "⛔ The figures below may be unreliable: "
        f"{len(lines)} blocking check(s) failed.\n\n{bullets}"
    )


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
