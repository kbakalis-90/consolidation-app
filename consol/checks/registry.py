"""Central place to run groups of checks and summarize the results."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from consol.checks import ingestion_checks, statement_checks
from consol.domain.statements import StatementsBundle
from consol.models.enums import CheckSeverity
from consol.models.results import CheckResult


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


def summarize(results: list[CheckResult]) -> CheckSummary:
    return CheckSummary(results=results)
