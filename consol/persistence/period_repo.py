"""Repository for periods."""

from __future__ import annotations

import sqlite3

from consol.models.entities import Period


def _row_to_period(row: sqlite3.Row) -> Period:
    return Period(
        period_id=row["period_id"],
        year=row["year"],
        month=row["month"],
        label=row["label"],
        is_closed=bool(row["is_closed"]),
    )


def get_or_create(conn: sqlite3.Connection, year: int, month: int) -> int:
    """Return the period_id for (year, month), creating it if needed."""
    label = Period.make_label(year, month)
    conn.execute(
        "INSERT INTO period(year, month, label) VALUES(?, ?, ?) "
        "ON CONFLICT(year, month) DO NOTHING",
        (year, month, label),
    )
    row = conn.execute(
        "SELECT period_id FROM period WHERE year = ? AND month = ?", (year, month)
    ).fetchone()
    return int(row["period_id"])


def get_by_id(conn: sqlite3.Connection, period_id: int) -> Period | None:
    row = conn.execute("SELECT * FROM period WHERE period_id = ?", (period_id,)).fetchone()
    return _row_to_period(row) if row else None


def find(conn: sqlite3.Connection, year: int, month: int) -> Period | None:
    row = conn.execute(
        "SELECT * FROM period WHERE year = ? AND month = ?", (year, month)
    ).fetchone()
    return _row_to_period(row) if row else None


def list_all(conn: sqlite3.Connection) -> list[Period]:
    rows = conn.execute("SELECT * FROM period ORDER BY year, month").fetchall()
    return [_row_to_period(r) for r in rows]
