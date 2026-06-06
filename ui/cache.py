"""Cached wrappers around the heavy service read paths used by the UI pages.

Every wrapper takes only scalar arguments (scope/year/month/entity_id as
applicable) plus a ``data_version`` token and resolves the SQLite connection
internally via :func:`ui.bootstrap.get_conn`. The connection is deliberately
*not* a cache key — it is a process-wide resource, not data.

Cache invalidation: ``data_version`` is the latest ``upload_id`` from
``upload_log``. Any new upload bumps the token, so every cached read for the new
token is recomputed while older results stay cached. Pass the value from
:func:`data_version` as the last positional argument to each wrapper.

Returned report objects are plain dataclasses / pandas frames and are only
displayed (never mutated), so caching them is safe.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from consol.services.cashflow_service import (
    ConsolidatedCashflowReport,
    EntityCashflowReport,
)
from consol.services.cashflow_service import (
    build_consolidated_cashflow as _build_consolidated_cashflow,
)
from consol.services.cashflow_service import (
    build_entity_cashflow as _build_entity_cashflow,
)
from consol.services.comparatives_service import (
    ComparativeReport,
)
from consol.services.comparatives_service import (
    build_consolidated_comparatives as _build_consolidated_comparatives,
)
from consol.services.comparatives_service import (
    build_entity_comparatives as _build_entity_comparatives,
)
from consol.services.consolidation_service import (
    ConsolidationReport,
)
from consol.services.consolidation_service import (
    build_consolidation as _build_consolidation,
)
from consol.services.dashboard_service import (
    DashboardReport,
)
from consol.services.dashboard_service import (
    build_dashboard as _build_dashboard,
)
from consol.services.dashboard_service import (
    collect_all_checks as _collect_all_checks,
)
from consol.services.reporting_service import (
    EntityReport,
)
from consol.services.reporting_service import (
    build_entity_report as _build_entity_report,
)
from ui.bootstrap import get_conn


def data_version() -> int:
    """Return the latest ``upload_id`` as a cache-invalidation token.

    Kept here (not in a backend repo) so no persistence file needs editing.
    """
    conn = get_conn()
    row = conn.execute("SELECT COALESCE(MAX(upload_id), 0) FROM upload_log").fetchone()
    return int(row[0]) if row is not None else 0


@st.cache_data
def build_consolidation(year: int, month: int, data_version: int) -> ConsolidationReport:
    return _build_consolidation(get_conn(), year, month)


@st.cache_data
def build_dashboard(
    scope: str, year: int, month: int, entity_id: int | None, data_version: int
) -> DashboardReport:
    return _build_dashboard(get_conn(), scope, year, month, entity_id)


@st.cache_data
def build_entity_cashflow(
    entity_id: int, year: int, month: int, data_version: int
) -> EntityCashflowReport:
    return _build_entity_cashflow(get_conn(), entity_id, year, month)


@st.cache_data
def build_consolidated_cashflow(
    year: int, month: int, data_version: int
) -> ConsolidatedCashflowReport:
    return _build_consolidated_cashflow(get_conn(), year, month)


@st.cache_data
def build_entity_comparatives(
    entity_id: int, year: int, month: int, data_version: int
) -> ComparativeReport:
    return _build_entity_comparatives(get_conn(), entity_id, year, month)


@st.cache_data
def build_consolidated_comparatives(year: int, month: int, data_version: int) -> ComparativeReport:
    return _build_consolidated_comparatives(get_conn(), year, month)


@st.cache_data
def build_entity_report(entity_id: int, year: int, month: int, data_version: int) -> EntityReport:
    return _build_entity_report(get_conn(), entity_id, year, month)


@st.cache_data
def collect_all_checks(year: int, month: int, data_version: int) -> pd.DataFrame:
    return _collect_all_checks(get_conn(), year, month)
