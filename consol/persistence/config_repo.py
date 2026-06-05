"""Read/write the key/value ``config`` table (runtime source of truth)."""

from __future__ import annotations

import sqlite3

from consol.config import SETTINGS


def get(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
    return row["value"] if row is not None else default


def set(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO config(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def group_currency(conn: sqlite3.Connection) -> str:
    return get(conn, "group_currency", SETTINGS.group_currency) or SETTINGS.group_currency


def balance_tolerance(conn: sqlite3.Connection) -> float:
    return float(get(conn, "balance_tolerance", str(SETTINGS.balance_tolerance)))


def reconciliation_tolerance(conn: sqlite3.Connection) -> float:
    return float(get(conn, "reconciliation_tolerance", str(SETTINGS.reconciliation_tolerance)))


def fx_direction(conn: sqlite3.Connection) -> str:
    return get(conn, "fx_direction", SETTINGS.fx_direction) or SETTINGS.fx_direction
