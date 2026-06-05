"""Result objects returned by the domain layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from consol.models.enums import CheckSeverity, StatementType


@dataclass
class StatementResult:
    """A built statement (BS or PL) for one entity/period in one currency.

    ``lines`` is a tidy DataFrame with at least columns:
    ``caption, caption_order, amount``. ``currency`` records the basis the
    amounts are expressed in (local code or the group currency).
    """

    statement: StatementType
    currency: str
    lines: pd.DataFrame
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def total(self) -> float:
        return float(self.lines["amount"].sum()) if not self.lines.empty else 0.0

    def caption_amount(self, caption: str) -> float:
        sel = self.lines.loc[self.lines["caption"] == caption, "amount"]
        return float(sel.sum())


@dataclass
class CheckResult:
    """Outcome of a single accuracy/integrity check."""

    check_id: str
    description: str
    severity: CheckSeverity
    passed: bool
    detail: str = ""
    # Optional offending rows to help the user locate the problem.
    rows: pd.DataFrame | None = None

    @property
    def is_blocking(self) -> bool:
        return self.severity == CheckSeverity.ERROR and not self.passed


@dataclass
class ConsolidationResult:
    """Consolidated statements plus the artefacts that produced them."""

    balance_sheet: StatementResult
    profit_and_loss: StatementResult
    eliminations: pd.DataFrame
    ic_reconciliation: pd.DataFrame
    cta_rollforward: pd.DataFrame
    meta: dict[str, Any] = field(default_factory=dict)
