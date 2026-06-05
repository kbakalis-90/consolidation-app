"""Build per-entity cash flow statements (indirect and direct) for a period."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

import pandas as pd

from consol.checks import registry
from consol.domain.cashflow_direct import build_direct_cashflow
from consol.domain.cashflow_indirect import SECTION_FX, build_indirect_cashflow
from consol.domain.statements import StatementsBundle, build_statements, caption_attributes
from consol.domain.translation import convert
from consol.models.entities import Entity
from consol.models.results import CashFlowResult
from consol.persistence import (
    cash_repo,
    config_repo,
    entity_repo,
    fx_repo,
    mapping_repo,
    period_repo,
    tb_repo,
)


@dataclass
class EntityCashflowReport:
    entity: Entity
    period_label: str
    currency: str
    indirect: CashFlowResult | None
    direct: CashFlowResult | None
    checks: registry.CheckSummary
    has_prior: bool


class CashflowError(RuntimeError):
    """Raised when the current period's data is missing."""


def _cash_total(bundle: StatementsBundle, attrs) -> float:
    lines = bundle.balance_sheet.lines.merge(attrs, on="caption", how="left")
    cash = lines[lines["is_cash"].fillna(0).astype(int) == 1]
    return float(cash["amount"].sum())


def _bundle_for(
    conn: sqlite3.Connection, entity: Entity, period_id: int
) -> StatementsBundle | None:
    tb = tb_repo.load(conn, entity.entity_id, period_id)
    if tb.empty:
        return None
    mapping = mapping_repo.load_for_entity(conn, entity.entity_id)
    return build_statements(tb, mapping, entity.local_currency)


def build_entity_cashflow(
    conn: sqlite3.Connection, entity_id: int, year: int, month: int
) -> EntityCashflowReport:
    entity = entity_repo.get_by_id(conn, entity_id)
    if entity is None:
        raise CashflowError(f"Entity {entity_id} not found.")
    period = period_repo.find(conn, year, month)
    if period is None:
        raise CashflowError(f"No data for period {year}-{month:02d}.")

    current = _bundle_for(conn, entity, period.period_id)
    if current is None:
        raise CashflowError(f"No trial balance for {entity.code} in {period.label}.")

    mapping = mapping_repo.load_for_entity(conn, entity.entity_id)
    attrs = caption_attributes(mapping)
    tol = config_repo.balance_tolerance(conn)

    prior = period_repo.find(conn, *period.prior_month())
    prior_bundle = _bundle_for(conn, entity, prior.period_id) if prior else None
    has_prior = prior_bundle is not None

    indirect: CashFlowResult | None = None
    if has_prior:
        indirect = build_indirect_cashflow(
            current.balance_sheet, prior_bundle.balance_sheet, attrs, entity.local_currency
        )

    closing_cash = _cash_total(current, attrs)
    opening_cash = _cash_total(prior_bundle, attrs) if prior_bundle else 0.0

    direct: CashFlowResult | None = None
    cash = cash_repo.load(conn, entity.entity_id, period.period_id)
    if not cash.empty:
        direct = build_direct_cashflow(cash, entity.local_currency, opening_cash, closing_cash)

    results = registry.run_cashflow_checks(indirect, direct, has_prior, tol)

    return EntityCashflowReport(
        entity=entity,
        period_label=period.label,
        currency=entity.local_currency,
        indirect=indirect,
        direct=direct,
        checks=registry.summarize(results),
        has_prior=has_prior,
    )


@dataclass
class ConsolidatedCashflowReport:
    period_label: str
    group_currency: str
    indirect: CashFlowResult | None
    checks: registry.CheckSummary
    skipped: list[str] = field(default_factory=list)


def build_consolidated_cashflow(
    conn: sqlite3.Connection, year: int, month: int
) -> ConsolidatedCashflowReport:
    """Consolidated indirect cash flow: sum translated entity flows + an FX-effect line."""
    period = period_repo.find(conn, year, month)
    if period is None:
        raise CashflowError(f"No data for period {year}-{month:02d}.")

    group_ccy = config_repo.group_currency(conn)
    direction = config_repo.fx_direction(conn)
    tol = config_repo.balance_tolerance(conn)
    prior = period_repo.find(conn, *period.prior_month())

    frames: list[pd.DataFrame] = []
    opening_group = 0.0
    closing_group = 0.0
    skipped: list[str] = []

    if prior is None:
        return ConsolidatedCashflowReport(
            period.label,
            group_ccy,
            None,
            registry.summarize(registry.run_cashflow_checks(None, None, False, tol)),
            [e.code for e in entity_repo.list_all(conn, active_only=True)],
        )

    for entity in entity_repo.list_all(conn, active_only=True):
        current = _bundle_for(conn, entity, period.period_id)
        prior_bundle = _bundle_for(conn, entity, prior.period_id)
        if current is None or prior_bundle is None:
            skipped.append(entity.code)
            continue
        attrs = caption_attributes(mapping_repo.load_for_entity(conn, entity.entity_id))
        local_cf = build_indirect_cashflow(
            current.balance_sheet, prior_bundle.balance_sheet, attrs, entity.local_currency
        )

        closing_rate, average_rate = _rate(conn, period.period_id, entity.local_currency, group_ccy)
        opening_rate = _opening_rate(
            conn, prior.period_id, entity.local_currency, group_ccy, closing_rate
        )

        lines = local_cf.lines.copy()
        if not lines.empty:
            lines["amount"] = [convert(a, average_rate, direction) for a in lines["amount"]]
            frames.append(lines)
        opening_group += convert(local_cf.opening_cash, opening_rate, direction)
        closing_group += convert(local_cf.closing_cash, closing_rate, direction)

    if not frames and not skipped:
        return ConsolidatedCashflowReport(
            period.label, group_ccy, None, registry.summarize([]), skipped
        )

    combined = (
        pd.concat(frames, ignore_index=True)
        if frames
        else pd.DataFrame(columns=["section", "line", "amount"])
    )
    agg = (
        combined.groupby(["section", "line"], as_index=False)["amount"].sum()
        if not combined.empty
        else combined
    )
    translated_net = float(agg["amount"].sum()) if not agg.empty else 0.0

    movement = closing_group - opening_group
    fx_effect = movement - translated_net
    fx_row = pd.DataFrame(
        [{"section": SECTION_FX, "line": "Effect of exchange rates on cash", "amount": fx_effect}]
    )
    agg = pd.concat([agg, fx_row], ignore_index=True)

    indirect = CashFlowResult(
        method="indirect",
        currency=group_ccy,
        lines=agg,
        net_change=translated_net + fx_effect,
        opening_cash=opening_group,
        closing_cash=closing_group,
        meta={"fx_effect": fx_effect},
    )
    results = registry.run_cashflow_checks(indirect, None, True, tol)
    return ConsolidatedCashflowReport(
        period.label, group_ccy, indirect, registry.summarize(results), skipped
    )


def _rate(
    conn: sqlite3.Connection, period_id: int, currency: str, group_ccy: str
) -> tuple[float, float]:
    if currency == group_ccy:
        return 1.0, 1.0
    rate = fx_repo.get_rate(conn, period_id, currency)
    return rate if rate is not None else (1.0, 1.0)


def _opening_rate(
    conn: sqlite3.Connection,
    prior_period_id: int,
    currency: str,
    group_ccy: str,
    fallback: float,
) -> float:
    if currency == group_ccy:
        return 1.0
    rate = fx_repo.get_rate(conn, prior_period_id, currency)
    return rate[0] if rate is not None else fallback
