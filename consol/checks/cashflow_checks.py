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


def consolidated_indirect_ties_to_cash(cf: CashFlowResult, tolerance: float) -> CheckResult:
    """Validate the consolidated indirect statement without relying on the FX plug.

    On the consolidated path the FX-effect line is constructed as
    ``movement - translated_net`` so ``net_change`` equals the cash movement by
    construction; the plain :func:`indirect_ties_to_cash` therefore can never fail.

    This check instead anchors to two *independent* quantities recorded on the
    result meta by the service:

    * ``section_sum`` -- the operating/investing/financing section totals summed
      back up, which must equal ``translated_net`` (no flow lost or double-counted
      before the plug is added); and
    * ``expected_fx_effect`` -- the FX-on-cash expectation derived purely from the
      closing/opening-vs-average rate spreads on each entity's cash, which must
      equal the booked ``fx_effect`` plug.

    A genuine asymmetry (a dropped section, or an FX plug that is absorbing a real
    reconciliation gap rather than rate movement) makes one of these diverge.
    """
    translated_net = float(cf.meta.get("translated_net", 0.0))
    section_sum = float(cf.meta.get("section_sum", 0.0))
    fx_effect = float(cf.meta.get("fx_effect", 0.0))
    expected_fx = float(cf.meta.get("expected_fx_effect", 0.0))

    section_diff = section_sum - translated_net
    fx_diff = fx_effect - expected_fx
    passed = abs(section_diff) <= tolerance and abs(fx_diff) <= tolerance
    return CheckResult(
        check_id="consolidated_indirect_ties_to_cash",
        description="Consolidated indirect cash flow ties to its sections and FX spread",
        severity=CheckSeverity.ERROR,
        passed=passed,
        detail=(
            "Consolidated indirect cash flow reconciles (sections and FX spread)."
            if passed
            else (
                f"Section sum {section_sum:,.2f} vs translated net {translated_net:,.2f} "
                f"(diff {section_diff:,.2f}); FX plug {fx_effect:,.2f} vs expected "
                f"{expected_fx:,.2f} (diff {fx_diff:,.2f})."
            )
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
