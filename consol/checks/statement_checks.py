"""Checks on built statements."""

from __future__ import annotations

from consol.domain.statements import StatementsBundle
from consol.models.enums import CheckSeverity
from consol.models.results import CheckResult


def bs_balances(bundle: StatementsBundle, tolerance: float) -> CheckResult:
    """Total assets must equal total liabilities + equity (incl. period result)."""
    diff = bundle.total_assets - bundle.total_liabilities_equity
    passed = abs(diff) <= tolerance
    return CheckResult(
        check_id="bs_balances",
        description="Balance sheet balances (Assets = Liabilities + Equity)",
        severity=CheckSeverity.ERROR,
        passed=passed,
        detail=(
            (
                f"Assets {bundle.total_assets:,.2f} vs Liab+Equity "
                f"{bundle.total_liabilities_equity:,.2f}; difference {diff:,.2f}."
            )
            if not passed
            else "Balance sheet balances."
        ),
    )
