"""Unit tests for the pure blocking-banner decision logic.

These exercise ``blocking_banner_lines`` directly (no running Streamlit server):
it is the pure function that decides whether a banner shows and what it says.
"""

from __future__ import annotations

from consol.checks.registry import CheckSummary
from consol.models.enums import CheckSeverity
from consol.models.results import CheckResult
from ui.components.check_badge import blocking_banner_lines


def _result(
    *, passed: bool, severity: CheckSeverity, description: str, detail: str = ""
) -> CheckResult:
    return CheckResult(
        check_id=description.lower().replace(" ", "_"),
        description=description,
        severity=severity,
        passed=passed,
        detail=detail,
    )


def test_no_results_is_no_op() -> None:
    assert blocking_banner_lines(CheckSummary(results=[])) == []


def test_all_passed_is_no_op() -> None:
    summary = CheckSummary(
        results=[_result(passed=True, severity=CheckSeverity.ERROR, description="BS balances")]
    )
    assert summary.has_blocking_errors is False
    assert blocking_banner_lines(summary) == []


def test_only_warnings_is_no_op() -> None:
    summary = CheckSummary(
        results=[_result(passed=False, severity=CheckSeverity.WARNING, description="Prior period")]
    )
    assert blocking_banner_lines(summary) == []


def test_failed_error_with_detail() -> None:
    summary = CheckSummary(
        results=[
            _result(
                passed=False,
                severity=CheckSeverity.ERROR,
                description="BS balances",
                detail="off by 12.00",
            )
        ]
    )
    assert blocking_banner_lines(summary) == ["BS balances — off by 12.00"]


def test_failed_error_without_detail() -> None:
    summary = CheckSummary(
        results=[_result(passed=False, severity=CheckSeverity.ERROR, description="BS balances")]
    )
    assert blocking_banner_lines(summary) == ["BS balances"]


def test_only_failed_errors_included() -> None:
    summary = CheckSummary(
        results=[
            _result(passed=True, severity=CheckSeverity.ERROR, description="passed error"),
            _result(passed=False, severity=CheckSeverity.WARNING, description="failed warning"),
            _result(passed=False, severity=CheckSeverity.ERROR, description="failed error"),
        ]
    )
    assert blocking_banner_lines(summary) == ["failed error"]
