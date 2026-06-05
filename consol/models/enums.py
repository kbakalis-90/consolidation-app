"""Enumerations shared across the domain. Values match what is stored in SQLite."""

from __future__ import annotations

from enum import StrEnum


class StatementType(StrEnum):
    BS = "BS"  # Balance Sheet
    PL = "PL"  # Profit & Loss


class CFCategory(StrEnum):
    OPERATING = "operating"
    INVESTING = "investing"
    FINANCING = "financing"


class WCClass(StrEnum):
    """Working-capital classification, used by the indirect cash flow."""

    AR = "AR"  # trade & other receivables
    AP = "AP"  # trade & other payables
    INVENTORY = "inventory"
    OTHER_WC = "other_wc"


class NormalSign(StrEnum):
    DEBIT = "debit"
    CREDIT = "credit"


class FlowSign(StrEnum):
    RECEIPT = "receipt"
    PAYMENT = "payment"


class ICType(StrEnum):
    RECEIVABLE = "receivable"
    PAYABLE = "payable"
    INCOME = "income"
    EXPENSE = "expense"


class CheckSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
