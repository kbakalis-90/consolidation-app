"""Assemble actual-vs-comparative tables (prior month, prior year, budget)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import pandas as pd

from consol.checks import ingestion_checks, registry
from consol.domain.statements import StatementsBundle, build_statements
from consol.domain.variance import build_variance
from consol.models.entities import Entity
from consol.persistence import budget_repo, entity_repo, mapping_repo, period_repo, tb_repo
from consol.services.consolidation_service import build_consolidation

_BS_KEYS = ["section", "caption"]
_PL_KEYS = ["caption"]


@dataclass
class ComparativeReport:
    title: str
    period_label: str
    currency: str
    bs_variance: pd.DataFrame
    pl_variance: pd.DataFrame
    checks: registry.CheckSummary
    available: dict[str, bool]


class ComparativesError(RuntimeError):
    pass


def _bundle_from_tb(conn, entity: Entity, period_id: int) -> StatementsBundle | None:
    tb = tb_repo.load(conn, entity.entity_id, period_id)
    if tb.empty:
        return None
    mapping = mapping_repo.load_for_entity(conn, entity.entity_id)
    return build_statements(tb, mapping, entity.local_currency)


def _budget_bundle(conn, entity: Entity, period_id: int) -> StatementsBundle | None:
    budget = budget_repo.load(conn, entity.entity_id, period_id)
    if budget.empty:
        return None
    mapping = mapping_repo.load_for_entity(conn, entity.entity_id)
    return build_statements(budget, mapping, entity.local_currency)


def build_entity_comparatives(
    conn: sqlite3.Connection, entity_id: int, year: int, month: int
) -> ComparativeReport:
    entity = entity_repo.get_by_id(conn, entity_id)
    if entity is None:
        raise ComparativesError(f"Entity {entity_id} not found.")
    period = period_repo.find(conn, year, month)
    if period is None:
        raise ComparativesError(f"No data for period {year}-{month:02d}.")

    current = _bundle_from_tb(conn, entity, period.period_id)
    if current is None:
        raise ComparativesError(f"No trial balance for {entity.code} in {period.label}.")

    pm = period_repo.find(conn, *period.prior_month())
    py = period_repo.find(conn, *period.prior_year())
    prior_month = _bundle_from_tb(conn, entity, pm.period_id) if pm else None
    prior_year = _bundle_from_tb(conn, entity, py.period_id) if py else None
    budget = _budget_bundle(conn, entity, period.period_id)

    available = {
        "Prior month": prior_month is not None,
        "Prior year": prior_year is not None,
        "Budget": budget is not None,
    }

    bs_var = _variance_for(current, prior_month, prior_year, budget, "balance_sheet", _BS_KEYS)
    pl_var = _variance_for(current, prior_month, prior_year, budget, "profit_and_loss", _PL_KEYS)

    checks = registry.summarize(
        [ingestion_checks.budget_completeness(budget is not None, period.label)]
    )

    return ComparativeReport(
        title=f"{entity.code} — {entity.name}",
        period_label=period.label,
        currency=entity.local_currency,
        bs_variance=bs_var,
        pl_variance=pl_var,
        checks=checks,
        available=available,
    )


def build_consolidated_comparatives(
    conn: sqlite3.Connection, year: int, month: int
) -> ComparativeReport:
    period = period_repo.find(conn, year, month)
    if period is None:
        raise ComparativesError(f"No data for period {year}-{month:02d}.")

    current = build_consolidation(conn, year, month)
    if current.result is None:
        raise ComparativesError("Nothing to consolidate for this period.")

    pm = period_repo.find(conn, *period.prior_month())
    py = period_repo.find(conn, *period.prior_year())
    prior_month = build_consolidation(conn, pm.year, pm.month).result if pm else None
    prior_year = build_consolidation(conn, py.year, py.month).result if py else None

    available = {
        "Prior month": prior_month is not None,
        "Prior year": prior_year is not None,
    }

    def _lines(res, attr):
        return getattr(res, attr).lines if res is not None else None

    bs_var = build_variance(
        current.result.balance_sheet.lines,
        _present(
            {
                "Prior month": _lines(prior_month, "balance_sheet"),
                "Prior year": _lines(prior_year, "balance_sheet"),
            }
        ),
        _BS_KEYS,
    )
    pl_var = build_variance(
        current.result.profit_and_loss.lines,
        _present(
            {
                "Prior month": _lines(prior_month, "profit_and_loss"),
                "Prior year": _lines(prior_year, "profit_and_loss"),
            }
        ),
        _PL_KEYS,
    )

    return ComparativeReport(
        title="Consolidated group",
        period_label=period.label,
        currency=current.group_currency,
        bs_variance=bs_var,
        pl_variance=pl_var,
        checks=registry.summarize([]),
        available=available,
    )


def _variance_for(current, prior_month, prior_year, budget, attr, keys) -> pd.DataFrame:
    comparatives = _present(
        {
            "Prior month": getattr(prior_month, attr).lines if prior_month else None,
            "Prior year": getattr(prior_year, attr).lines if prior_year else None,
            "Budget": getattr(budget, attr).lines if budget else None,
        }
    )
    return build_variance(getattr(current, attr).lines, comparatives, keys)


def _present(d: dict[str, pd.DataFrame | None]) -> dict[str, pd.DataFrame]:
    return {k: v for k, v in d.items() if v is not None}
