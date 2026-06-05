"""Shared vocabulary: enums and dataclasses used across layers."""

from consol.models.entities import Entity, Period
from consol.models.enums import (
    CFCategory,
    CheckSeverity,
    FlowSign,
    ICType,
    NormalSign,
    StatementType,
    WCClass,
)
from consol.models.results import CheckResult, ConsolidationResult, StatementResult

__all__ = [
    "Entity",
    "Period",
    "StatementType",
    "CFCategory",
    "WCClass",
    "NormalSign",
    "FlowSign",
    "ICType",
    "CheckSeverity",
    "StatementResult",
    "CheckResult",
    "ConsolidationResult",
]
