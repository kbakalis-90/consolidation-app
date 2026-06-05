"""Build the consolidated pack for a period: translate every entity, then consolidate."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from consol.checks import ingestion_checks, registry
from consol.domain.consolidation import consolidate
from consol.domain.statements import build_statements
from consol.domain.translation import TranslatedEntity, translate_bundle
from consol.models.results import ConsolidationResult
from consol.persistence import (
    config_repo,
    entity_repo,
    fx_repo,
    ic_repo,
    mapping_repo,
    period_repo,
    tb_repo,
)


@dataclass
class ConsolidationReport:
    period_label: str
    group_currency: str
    result: ConsolidationResult | None
    translated: list[TranslatedEntity]
    checks: registry.CheckSummary
    missing_tb: list[str] = field(default_factory=list)


class ConsolidationError(RuntimeError):
    """Raised when the consolidation cannot be built at all."""


def _resolve_rate(
    conn: sqlite3.Connection, period_id: int, currency: str, group_ccy: str
) -> tuple[float, float]:
    """Closing/average rate for a currency; the group currency is always (1, 1)."""
    if currency == group_ccy:
        return 1.0, 1.0
    rate = fx_repo.get_rate(conn, period_id, currency)
    return rate if rate is not None else (1.0, 1.0)


def _historical_rate(
    conn: sqlite3.Connection,
    prior_period_id: int | None,
    currency: str,
    group_ccy: str,
    fallback_closing: float,
) -> float:
    """Opening rate proxy for equity: prior period's closing rate if available."""
    if currency == group_ccy:
        return 1.0
    if prior_period_id is not None:
        rate = fx_repo.get_rate(conn, prior_period_id, currency)
        if rate is not None:
            return rate[0]
    return fallback_closing


def build_consolidation(conn: sqlite3.Connection, year: int, month: int) -> ConsolidationReport:
    period = period_repo.find(conn, year, month)
    if period is None:
        raise ConsolidationError(f"No data for period {year}-{month:02d}.")

    group_ccy = config_repo.group_currency(conn)
    direction = config_repo.fx_direction(conn)
    tol = config_repo.balance_tolerance(conn)
    recon_tol = config_repo.reconciliation_tolerance(conn)

    entities = entity_repo.list_all(conn, active_only=True)
    rates_df = fx_repo.load_for_period(conn, period.period_id)

    needed = {e.local_currency for e in entities}
    fx_check = ingestion_checks.fx_completeness(needed, rates_df, group_ccy, tol)

    prior = period_repo.find(conn, *period.prior_month())
    prior_id = prior.period_id if prior else None

    translated: list[TranslatedEntity] = []
    missing_tb: list[str] = []
    fx_rates: dict[str, tuple[float, float]] = {}

    for entity in entities:
        tb = tb_repo.load(conn, entity.entity_id, period.period_id)
        if tb.empty:
            missing_tb.append(entity.code)
            continue
        mapping = mapping_repo.load_for_entity(conn, entity.entity_id)
        bundle = build_statements(tb, mapping, entity.local_currency)

        closing, average = _resolve_rate(conn, period.period_id, entity.local_currency, group_ccy)
        fx_rates[entity.local_currency] = (closing, average)
        historical = _historical_rate(conn, prior_id, entity.local_currency, group_ccy, closing)
        translated.append(
            translate_bundle(bundle, entity, closing, average, group_ccy, direction, historical)
        )

    if not translated:
        return ConsolidationReport(
            period.label, group_ccy, None, [], registry.summarize([fx_check]), missing_tb
        )

    ic = ic_repo.load_for_period(conn, period.period_id)
    result = consolidate(translated, ic, fx_rates, group_ccy, direction)

    results = [fx_check]
    results += registry.run_consolidation_checks(translated, result, tol, recon_tol)

    return ConsolidationReport(
        period_label=period.label,
        group_currency=group_ccy,
        result=result,
        translated=translated,
        checks=registry.summarize(results),
        missing_tb=missing_tb,
    )
