"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from consol.persistence import db
from consol.persistence.migrations import apply_schema

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def conn():
    """An in-memory SQLite connection with the schema applied."""
    c = db.connect(":memory:")
    apply_schema(c)
    yield c
    c.close()


@pytest.fixture
def sample_tb() -> pd.DataFrame:
    """Canonical TB (debit +, credit -) matching the fixture CSV."""
    return pd.DataFrame(
        {
            "account_code": ["1000", "1100", "2000", "3000", "4000", "5000"],
            "account_desc": [
                "Cash",
                "Receivables",
                "Payables",
                "Share capital",
                "Revenue",
                "Operating expenses",
            ],
            "amount_local": [500.0, 300.0, -200.0, -400.0, -600.0, 400.0],
        }
    )


@pytest.fixture
def sample_mapping() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "account_code": ["1000", "1100", "2000", "3000", "4000", "5000"],
            "account_desc": [
                "Cash",
                "Receivables",
                "Payables",
                "Share capital",
                "Revenue",
                "Operating expenses",
            ],
            "statement": ["BS", "BS", "BS", "BS", "PL", "PL"],
            "caption": [
                "Cash and cash equivalents",
                "Trade receivables",
                "Trade payables",
                "Share capital",
                "Revenue",
                "Operating expenses",
            ],
            "caption_order": [1, 2, 3, 4, 1, 2],
            "cf_category": [None, None, None, None, "operating", "operating"],
            "wc_class": [None, "AR", "AP", None, None, None],
            "normal_sign": ["debit", "debit", "credit", "credit", "credit", "debit"],
            "is_equity": [0, 0, 0, 1, 0, 0],
            "is_cash": [1, 0, 0, 0, 0, 0],
        }
    )


@pytest.fixture
def tb_csv_bytes() -> bytes:
    return (FIXTURES / "entity_A_tb_2026-01.csv").read_bytes()


@pytest.fixture
def mapping_csv_bytes() -> bytes:
    return (FIXTURES / "entity_A_mapping.csv").read_bytes()
