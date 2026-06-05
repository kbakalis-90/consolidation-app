"""Apply the schema. The schema is idempotent, so this can run on every start."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from consol.config import SETTINGS

_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def apply_schema(conn: sqlite3.Connection) -> None:
    """Create all tables if they do not already exist and seed config defaults."""
    conn.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))
    _seed_config(conn)
    conn.commit()


def _seed_config(conn: sqlite3.Connection) -> None:
    defaults = {
        "group_currency": SETTINGS.group_currency,
        "fx_direction": SETTINGS.fx_direction,
        "balance_tolerance": str(SETTINGS.balance_tolerance),
        "reconciliation_tolerance": str(SETTINGS.reconciliation_tolerance),
    }
    for key, value in defaults.items():
        conn.execute(
            "INSERT INTO config(key, value) VALUES(?, ?) ON CONFLICT(key) DO NOTHING",
            (key, value),
        )
