"""Checks on raw ingested data (TB + mapping)."""

from __future__ import annotations

import pandas as pd

from consol.ingestion.validators import find_duplicates
from consol.models.enums import CheckSeverity
from consol.models.results import CheckResult


def tb_balances(tb: pd.DataFrame, tolerance: float) -> CheckResult:
    """Trial balance debits must equal credits (signed sum ~ 0)."""
    total = float(tb["amount_local"].sum()) if not tb.empty else 0.0
    passed = abs(total) <= tolerance
    return CheckResult(
        check_id="tb_balances",
        description="Trial balance debits equal credits",
        severity=CheckSeverity.ERROR,
        passed=passed,
        detail=(
            f"Signed TB total = {total:,.2f} (tolerance {tolerance})."
            if not passed
            else "TB is balanced."
        ),
    )


def all_accounts_mapped(tb: pd.DataFrame, mapping: pd.DataFrame) -> CheckResult:
    """Every TB account code must have a mapping row."""
    tb_codes = set(tb["account_code"].astype(str).str.strip())
    mapped_codes = (
        set(mapping["account_code"].astype(str).str.strip()) if not mapping.empty else set()
    )
    missing = sorted(tb_codes - mapped_codes)
    passed = not missing
    rows = pd.DataFrame({"unmapped_account_code": missing}) if missing else None
    return CheckResult(
        check_id="all_accounts_mapped",
        description="All trial-balance accounts are mapped",
        severity=CheckSeverity.ERROR,
        passed=passed,
        detail=(
            "All accounts mapped."
            if passed
            else f"{len(missing)} unmapped account(s): {', '.join(missing[:10])}"
            + ("..." if len(missing) > 10 else "")
        ),
        rows=rows,
    )


def no_duplicate_accounts(df: pd.DataFrame, source_label: str) -> CheckResult:
    """No account code should appear twice within a single file."""
    codes = df["account_code"].astype(str).str.strip()
    counts = codes.value_counts()
    dups = counts[counts > 1].index.tolist()
    passed = not dups
    return CheckResult(
        check_id=f"no_duplicate_accounts_{source_label}",
        description=f"No duplicate account codes in {source_label}",
        severity=CheckSeverity.ERROR,
        passed=passed,
        detail=(
            "No duplicates."
            if passed
            else f"Duplicate code(s) in {source_label}: {', '.join(map(str, dups[:10]))}"
        ),
    )


def sign_sanity(tb: pd.DataFrame, mapping: pd.DataFrame) -> CheckResult:
    """Warn where a balance's sign opposes the account's expected normal sign."""
    if mapping.empty:
        return CheckResult(
            "sign_sanity", "Account balances match expected sign", CheckSeverity.WARNING, True
        )
    merged = tb.merge(mapping[["account_code", "normal_sign"]], on="account_code", how="inner")
    # Debit-normal expects amount >= 0; credit-normal expects amount <= 0.
    wrong = merged[
        ((merged["normal_sign"].str.lower() == "debit") & (merged["amount_local"] < 0))
        | ((merged["normal_sign"].str.lower() == "credit") & (merged["amount_local"] > 0))
    ]
    passed = wrong.empty
    return CheckResult(
        check_id="sign_sanity",
        description="Account balances match expected sign",
        severity=CheckSeverity.WARNING,
        passed=passed,
        detail=(
            "All balances in expected direction."
            if passed
            else f"{len(wrong)} account(s) have a balance opposite to their normal sign."
        ),
        rows=wrong[["account_code", "normal_sign", "amount_local"]] if not passed else None,
    )


def budget_completeness(has_budget: bool, period_label: str) -> CheckResult:
    """Warn when a budget comparison is requested but no budget exists for the period."""
    return CheckResult(
        check_id="budget_completeness",
        description="Budget available for the period",
        severity=CheckSeverity.WARNING,
        passed=has_budget,
        detail=(
            "Budget present."
            if has_budget
            else f"No budget uploaded for {period_label}; budget variance unavailable."
        ),
    )


def fx_completeness(
    needed_currencies: set[str],
    rates: pd.DataFrame,
    group_currency: str,
    tolerance: float = 0.01,
) -> CheckResult:
    """Every entity currency must have a rate; the group currency must be 1.0.

    Used at consolidation time, where both concerns are blocking. The upload
    path uses the finer-grained :func:`fx_group_rate` (blocking) and
    :func:`fx_currencies_present` (warning) instead.
    """
    available = set(rates["currency"]) if not rates.empty else set()
    missing = sorted((needed_currencies - {group_currency}) - available)

    group_ok = True
    group_detail = ""
    if group_currency in available:
        grp = rates.loc[rates["currency"] == group_currency, ["closing_rate", "average_rate"]]
        if not ((grp.sub(1.0).abs() <= tolerance).all().all()):
            group_ok = False
            group_detail = f" Group currency {group_currency} rate must be 1.0."

    passed = not missing and group_ok
    detail = "All required FX rates present."
    if missing:
        detail = f"Missing FX rate(s) for: {', '.join(missing)}."
    detail += group_detail
    return CheckResult(
        check_id="fx_completeness",
        description="FX rates present for all entity currencies",
        severity=CheckSeverity.ERROR,
        passed=passed,
        detail=detail,
        rows=pd.DataFrame({"missing_currency": missing}) if missing else None,
    )


def fx_group_rate(
    rates: pd.DataFrame,
    group_currency: str,
    tolerance: float = 0.01,
) -> CheckResult:
    """The group currency, when present, must have a rate of ~1.0 (blocking).

    A wrong group rate silently mis-translates every entity, so at upload time
    this is an ERROR that rejects the file. Absence of the group currency is not
    blocking here (it is not strictly required to be in the file).
    """
    available = set(rates["currency"]) if not rates.empty else set()
    group_ok = True
    if group_currency in available:
        grp = rates.loc[rates["currency"] == group_currency, ["closing_rate", "average_rate"]]
        group_ok = bool((grp.sub(1.0).abs() <= tolerance).all().all())
    return CheckResult(
        check_id="fx_group_rate",
        description="Group currency rate is 1.0",
        severity=CheckSeverity.ERROR,
        passed=group_ok,
        detail=(
            f"Group currency {group_currency} rate is 1.0."
            if group_ok
            else f"Group currency {group_currency} closing/average rate must be 1.0."
        ),
    )


def fx_currencies_present(
    needed_currencies: set[str],
    rates: pd.DataFrame,
    group_currency: str,
) -> CheckResult:
    """Warn (do not block) when an entity currency has no rate in the file.

    At upload time not every entity may have been set up yet, so a missing rate
    is informational rather than a hard failure.
    """
    available = set(rates["currency"]) if not rates.empty else set()
    missing = sorted((needed_currencies - {group_currency}) - available)
    passed = not missing
    return CheckResult(
        check_id="fx_currencies_present",
        description="FX rates present for all entity currencies",
        severity=CheckSeverity.WARNING,
        passed=passed,
        detail=(
            "All entity-currency FX rates present."
            if passed
            else f"Missing FX rate(s) for: {', '.join(missing)}."
        ),
        rows=pd.DataFrame({"missing_currency": missing}) if missing else None,
    )


def ic_no_duplicates(ic: pd.DataFrame) -> CheckResult:
    """No duplicate IC line on the composite key (blocking).

    Duplicate lines on ``(entity_code, counterparty_code, ic_type, caption)``
    would either double-count or collide with the DB UNIQUE index, so this is a
    blocking ERROR.
    """
    keys = ["entity_code", "counterparty_code", "ic_type", "caption"]
    dups = find_duplicates(ic, keys)
    passed = dups.empty
    return CheckResult(
        check_id="ic_no_duplicates",
        description="No duplicate intercompany lines",
        severity=CheckSeverity.ERROR,
        passed=passed,
        detail=(
            "No duplicate IC lines."
            if passed
            else f"{len(dups)} duplicate IC line(s) on (entity, counterparty, type, caption)."
        ),
        rows=None if passed else dups,
    )
