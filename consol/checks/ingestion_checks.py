"""Checks on raw ingested data (TB + mapping)."""

from __future__ import annotations

import pandas as pd

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
