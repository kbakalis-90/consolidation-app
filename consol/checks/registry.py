"""Central place to run groups of checks and summarize the results."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from consol.checks import (
    cashflow_checks,
    consolidation_checks,
    ingestion_checks,
    statement_checks,
)
from consol.domain.statements import StatementsBundle
from consol.domain.translation import TranslatedEntity
from consol.models.enums import CheckSeverity
from consol.models.results import CashFlowResult, CheckResult, ConsolidationResult


@dataclass
class CheckSummary:
    results: list[CheckResult]

    @property
    def errors(self) -> list[CheckResult]:
        return [r for r in self.results if r.severity == CheckSeverity.ERROR and not r.passed]

    @property
    def warnings(self) -> list[CheckResult]:
        return [r for r in self.results if r.severity == CheckSeverity.WARNING and not r.passed]

    @property
    def has_blocking_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.results)

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "check": r.check_id,
                    "description": r.description,
                    "severity": r.severity.value,
                    "passed": r.passed,
                    "detail": r.detail,
                }
                for r in self.results
            ]
        )


def run_ingestion_checks(
    tb: pd.DataFrame, mapping: pd.DataFrame, tolerance: float
) -> list[CheckResult]:
    results = [
        ingestion_checks.tb_balances(tb, tolerance),
        ingestion_checks.no_duplicate_accounts(tb, "trial balance"),
        ingestion_checks.all_accounts_mapped(tb, mapping),
        ingestion_checks.sign_sanity(tb, mapping),
    ]
    if not mapping.empty:
        results.insert(2, ingestion_checks.no_duplicate_accounts(mapping, "mapping"))
    return results


def run_statement_checks(bundle: StatementsBundle, tolerance: float) -> list[CheckResult]:
    return [statement_checks.bs_balances(bundle, tolerance)]


def run_consolidation_checks(
    entities: list[TranslatedEntity],
    result: ConsolidationResult,
    tolerance: float,
    recon_tolerance: float,
) -> list[CheckResult]:
    return [
        consolidation_checks.entity_translated_balances(entities, tolerance),
        consolidation_checks.consolidated_bs_balances(result, tolerance),
        consolidation_checks.eliminations_net_to_zero(result, tolerance),
        consolidation_checks.ic_reconciliation(result, recon_tolerance),
    ]


def run_cashflow_checks(
    indirect: CashFlowResult | None,
    direct: CashFlowResult | None,
    has_prior: bool,
    tolerance: float,
) -> list[CheckResult]:
    results = [cashflow_checks.prior_period_present(has_prior)]
    if indirect is not None:
        results.append(cashflow_checks.indirect_ties_to_cash(indirect, tolerance))
    if direct is not None and has_prior:
        # Reconciling the direct method needs an opening cash balance (prior period).
        results.append(cashflow_checks.direct_ties_to_cash(direct, tolerance))
    if indirect is not None and direct is not None:
        results.append(cashflow_checks.indirect_equals_direct(indirect, direct, tolerance))
    return results


def summarize(results: list[CheckResult]) -> CheckSummary:
    return CheckSummary(results=results)
