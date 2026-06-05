"""Repository for FX rates (closing + average per currency per period)."""

from __future__ import annotations

import sqlite3

import pandas as pd


def replace_for_period(conn: sqlite3.Connection, period_id: int, rates: pd.DataFrame) -> int:
    """Replace all FX rows for a period. Columns: currency, closing_rate, average_rate."""
    conn.execute("DELETE FROM fx_rate WHERE period_id = ?", (period_id,))
    records = rates[["currency", "closing_rate", "average_rate"]].to_dict("records")
    conn.executemany(
        """
        INSERT INTO fx_rate(period_id, currency, closing_rate, average_rate)
        VALUES(:period_id, :currency, :closing_rate, :average_rate)
        """,
        [{"period_id": period_id, **r} for r in records],
    )
    return len(records)


def load_for_period(conn: sqlite3.Connection, period_id: int) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT currency, closing_rate, average_rate FROM fx_rate "
        "WHERE period_id = ? ORDER BY currency",
        conn,
        params=(period_id,),
    )


def get_rate(conn: sqlite3.Connection, period_id: int, currency: str) -> tuple[float, float] | None:
    """Return (closing_rate, average_rate) for a currency/period, or None."""
    row = conn.execute(
        "SELECT closing_rate, average_rate FROM fx_rate WHERE period_id = ? AND currency = ?",
        (period_id, currency),
    ).fetchone()
    return (float(row["closing_rate"]), float(row["average_rate"])) if row else None


def currencies_with_rates(conn: sqlite3.Connection, period_id: int) -> set[str]:
    rows = conn.execute("SELECT currency FROM fx_rate WHERE period_id = ?", (period_id,)).fetchall()
    return {r["currency"] for r in rows}
