"""KPIs and an aggregated accuracy-check panel."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import pandas as pd

from consol.checks import registry
from consol.domain.kpis import KPI, compute_kpis, revenue_growth
from consol.domain.statements import caption_attributes
from consol.models.results import CashFlowResult
from consol.persistence import entity_repo, mapping_repo, period_repo, tb_repo
from consol.services.cashflow_service import (
    build_consolidated_cashflow,
    build_entity_cashflow,
)
from consol.services.consolidation_service import build_consolidation
from consol.services.reporting_service import build_entity_report


@dataclass
class DashboardReport:
    title: str
    period_label: str
    currency: str
    kpis: list[KPI]
    revenue_growth: float | None
    checks: registry.CheckSummary


class DashboardError(RuntimeError):
    pass


def _combined_attrs(conn: sqlite3.Connection) -> pd.DataFrame:
    frames = [
        caption_attributes(mapping_repo.load_for_entity(conn, e.entity_id))
        for e in entity_repo.list_all(conn, active_only=True)
    ]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame(columns=["caption", "cf_category", "wc_class", "is_cash"])
    combined = pd.concat(frames, ignore_index=True)
    return combined.drop_duplicates(subset="caption", keep="first").reset_index(drop=True)


def build_dashboard(
    conn: sqlite3.Connection,
    scope: str,
    year: int,
    month: int,
    entity_id: int | None = None,
) -> DashboardReport:
    period = period_repo.find(conn, year, month)
    if period is None:
        raise DashboardError(f"No data for period {year}-{month:02d}.")

    if scope == "entity":
        if entity_id is None:
            raise DashboardError("An entity must be selected.")
        report = build_entity_report(conn, entity_id, year, month)
        bs, pl = report.bundle.balance_sheet, report.bundle.profit_and_loss
        attrs = caption_attributes(mapping_repo.load_for_entity(conn, entity_id))
        cf = _entity_cf(conn, entity_id, year, month)
        growth = _entity_growth(conn, entity_id, period)
        title = report.entity.name
        currency = report.entity.local_currency
        checks = report.checks
    else:
        consol = build_consolidation(conn, year, month)
        if consol.result is None:
            raise DashboardError("Nothing to consolidate for this period.")
        bs, pl = consol.result.balance_sheet, consol.result.profit_and_loss
        attrs = _combined_attrs(conn)
        cf = build_consolidated_cashflow(conn, year, month).indirect
        growth = None
        title = "Consolidated group"
        currency = consol.group_currency
        checks = consol.checks

    kpis = compute_kpis(bs, pl, attrs, cf)
    return DashboardReport(title, period.label, currency, kpis, growth, checks)


def _entity_cf(
    conn: sqlite3.Connection, entity_id: int, year: int, month: int
) -> CashFlowResult | None:
    try:
        return build_entity_cashflow(conn, entity_id, year, month).indirect
    except Exception:
        return None


def _entity_growth(conn: sqlite3.Connection, entity_id: int, period) -> float | None:
    entity = entity_repo.get_by_id(conn, entity_id)
    pm = period_repo.find(conn, *period.prior_month())
    if pm is None:
        return None
    try:
        cur = build_entity_report(conn, entity_id, period.year, period.month).bundle.profit_and_loss
        pri = build_entity_report(conn, entity_id, pm.year, pm.month).bundle.profit_and_loss
    except Exception:
        return None
    _ = entity
    return revenue_growth(cur, pri)


def collect_all_checks(conn: sqlite3.Connection, year: int, month: int) -> pd.DataFrame:
    """Run every applicable check for a period and tag each by scope."""
    rows: list[dict] = []

    period = period_repo.find(conn, year, month)
    if period is None:
        return pd.DataFrame(columns=["scope", "check", "severity", "passed", "detail"])

    for entity in entity_repo.list_all(conn, active_only=True):
        if not tb_repo.has_tb(conn, entity.entity_id, period.period_id):
            continue
        report = build_entity_report(conn, entity.entity_id, year, month)
        _extend(rows, entity.code, report.checks)
        try:
            cf = build_entity_cashflow(conn, entity.entity_id, year, month)
            _extend(rows, f"{entity.code} cash flow", cf.checks)
        except Exception:
            pass

    try:
        consol = build_consolidation(conn, year, month)
        _extend(rows, "Consolidation", consol.checks)
    except Exception:
        pass

    return pd.DataFrame(rows, columns=["scope", "check", "severity", "passed", "detail"])


def _extend(rows: list[dict], scope: str, summary: registry.CheckSummary) -> None:
    for r in summary.results:
        rows.append(
            {
                "scope": scope,
                "check": r.check_id,
                "severity": r.severity.value,
                "passed": r.passed,
                "detail": r.detail,
            }
        )
