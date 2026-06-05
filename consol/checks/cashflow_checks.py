"""Checks on cash flow statements."""

from __future__ import annotations

from consol.models.enums import CheckSeverity
from consol.models.results import CashFlowResult, CheckResult


def indirect_ties_to_cash(cf: CashFlowResult, tolerance: float) -> CheckResult:
    """Indirect net change must equal the movement in cash balances."""
    movement = cf.closing_cash - cf.opening_cash
    diff = cf.net_change - movement
    passed = abs(diff) <= tolerance
    return CheckResult(
        check_id="indirect_ties_to_cash",
        description="Indirect cash flow ties to the change in cash",
        severity=CheckSeverity.ERROR,
        passed=passed,
        detail=(
            f"Indirect net {cf.net_change:,.2f} vs cash movement {movement:,.2f}."
            if not passed
            else "Indirect cash flow reconciles to cash movement."
        ),
    )


def direct_ties_to_cash(cf: CashFlowResult, tolerance: float) -> CheckResult:
    movement = cf.closing_cash - cf.opening_cash
    diff = cf.net_change - movement
    passed = abs(diff) <= tolerance
    return CheckResult(
        check_id="direct_ties_to_cash",
        description="Direct cash flow ties to the change in cash",
        severity=CheckSeverity.ERROR,
        passed=passed,
        detail=(
            f"Direct net {cf.net_change:,.2f} vs cash movement {movement:,.2f}."
            if not passed
            else "Direct cash flow reconciles to cash movement."
        ),
    )


def indirect_equals_direct(
    indirect: CashFlowResult, direct: CashFlowResult, tolerance: float
) -> CheckResult:
    diff = indirect.net_change - direct.net_change
    passed = abs(diff) <= tolerance
    return CheckResult(
        check_id="indirect_equals_direct",
        description="Indirect and direct methods agree on net change in cash",
        severity=CheckSeverity.ERROR,
        passed=passed,
        detail=(
            f"Indirect {indirect.net_change:,.2f} vs direct {direct.net_change:,.2f}."
            if not passed
            else "Both methods agree."
        ),
    )


def prior_period_present(has_prior: bool) -> CheckResult:
    return CheckResult(
        check_id="prior_period_present",
        description="Prior period available for the indirect cash flow",
        severity=CheckSeverity.ERROR,
        passed=has_prior,
        detail=(
            "Prior period present."
            if has_prior
            else "No prior period uploaded; the indirect cash flow needs an opening balance sheet."
        ),
    )
