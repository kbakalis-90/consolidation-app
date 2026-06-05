"""Checks on translation and consolidation."""

from __future__ import annotations

from consol.domain.statements import SECTION_ASSETS, SECTION_LIABILITIES
from consol.domain.translation import TranslatedEntity
from consol.models.enums import CheckSeverity, StatementType
from consol.models.results import CheckResult, ConsolidationResult


def entity_translated_balances(entities: list[TranslatedEntity], tolerance: float) -> CheckResult:
    """Each translated entity balance sheet must balance after CTA."""
    offenders = [
        te.entity.code
        for te in entities
        if abs(te.total_assets - te.total_liabilities_equity) > tolerance
    ]
    passed = not offenders
    return CheckResult(
        check_id="entity_translated_balances",
        description="Each entity's translated balance sheet balances (incl. CTA)",
        severity=CheckSeverity.ERROR,
        passed=passed,
        detail=(
            "All translated entities balance."
            if passed
            else f"Translated BS does not balance for: {', '.join(offenders)}."
        ),
    )


def consolidated_bs_balances(result: ConsolidationResult, tolerance: float) -> CheckResult:
    ta = result.meta.get("total_assets", 0.0)
    tle = result.meta.get("total_liabilities_equity", 0.0)
    diff = ta - tle
    passed = abs(diff) <= tolerance
    return CheckResult(
        check_id="consolidated_bs_balances",
        description="Consolidated balance sheet balances",
        severity=CheckSeverity.ERROR,
        passed=passed,
        detail=(
            f"Assets {ta:,.2f} vs Liab+Equity {tle:,.2f}; difference {diff:,.2f}."
            if not passed
            else "Consolidated balance sheet balances."
        ),
    )


def eliminations_net_to_zero(result: ConsolidationResult, tolerance: float) -> CheckResult:
    """Asset-side BS eliminations must equal liability-side; same for P&L."""
    elim = result.eliminations
    if elim.empty:
        return CheckResult(
            "eliminations_net_to_zero",
            "Intercompany eliminations net to zero",
            CheckSeverity.ERROR,
            True,
            "No eliminations.",
        )
    bs = elim[elim["statement"] == StatementType.BS.value]
    asset_side = bs.loc[bs["section"] == SECTION_ASSETS, "amount"].sum()
    liab_side = bs.loc[bs["section"] == SECTION_LIABILITIES, "amount"].sum()
    pl = elim[elim["statement"] == StatementType.PL.value]
    pl_net = pl["amount"].sum()  # revenue (neg) + expense add-back (pos) should cancel
    bs_ok = abs(asset_side - liab_side) <= tolerance
    pl_ok = abs(pl_net) <= tolerance
    passed = bs_ok and pl_ok
    return CheckResult(
        check_id="eliminations_net_to_zero",
        description="Intercompany eliminations net to zero",
        severity=CheckSeverity.ERROR,
        passed=passed,
        detail=(
            "Eliminations balanced."
            if passed
            else f"BS asset-side {asset_side:,.2f} vs liability-side {liab_side:,.2f}; "
            f"P&L net {pl_net:,.2f}."
        ),
    )


def ic_reconciliation(result: ConsolidationResult, tolerance: float) -> CheckResult:
    """Warn where the two sides of an intercompany balance disagree."""
    recon = result.ic_reconciliation
    if recon.empty:
        return CheckResult(
            "ic_reconciliation",
            "Intercompany balances reconcile",
            CheckSeverity.WARNING,
            True,
            "No intercompany balances.",
        )
    mismatched = recon[
        (recon["bs_difference"].abs() > tolerance) | (recon["pnl_difference"].abs() > tolerance)
    ]
    passed = mismatched.empty
    return CheckResult(
        check_id="ic_reconciliation",
        description="Intercompany balances reconcile between counterparties",
        severity=CheckSeverity.WARNING,
        passed=passed,
        detail=(
            "All intercompany pairs reconcile."
            if passed
            else f"{len(mismatched)} intercompany pair(s) do not reconcile."
        ),
        rows=mismatched if not passed else None,
    )
