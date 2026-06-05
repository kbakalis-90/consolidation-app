"""Build single-entity statements for a period (local currency)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from consol.checks import registry
from consol.domain.statements import StatementsBundle, build_statements
from consol.models.entities import Entity
from consol.persistence import config_repo, entity_repo, mapping_repo, period_repo, tb_repo


@dataclass
class EntityReport:
    entity: Entity
    period_label: str
    bundle: StatementsBundle
    checks: registry.CheckSummary


class ReportingError(RuntimeError):
    """Raised when prerequisites for a report are missing."""


def build_entity_report(
    conn: sqlite3.Connection, entity_id: int, year: int, month: int
) -> EntityReport:
    entity = entity_repo.get_by_id(conn, entity_id)
    if entity is None:
        raise ReportingError(f"Entity {entity_id} not found.")
    period = period_repo.find(conn, year, month)
    if period is None:
        raise ReportingError(f"No data for period {year}-{month:02d}.")

    tb = tb_repo.load(conn, entity_id, period.period_id)
    if tb.empty:
        raise ReportingError(f"No trial balance uploaded for {entity.code} in {period.label}.")
    mapping = mapping_repo.load_for_entity(conn, entity_id)

    bundle = build_statements(tb, mapping, currency=entity.local_currency)

    tolerance = config_repo.balance_tolerance(conn)
    results = registry.run_ingestion_checks(tb, mapping, tolerance)
    results += registry.run_statement_checks(bundle, tolerance)
    summary = registry.summarize(results)

    return EntityReport(entity=entity, period_label=period.label, bundle=bundle, checks=summary)
