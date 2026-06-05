"""Repository for budget lines (stored per entity per period, like actuals)."""

from __future__ import annotations

import sqlite3

import pandas as pd


def replace_for_entity_periods(
    conn: sqlite3.Connection, entity_id: int, period_ids: list[int], budget: pd.DataFrame
) -> int:
    """Replace budget rows for an entity across the given periods.

    ``budget`` columns: period_id, account_code, amount_local.
    """
    conn.executemany(
        "DELETE FROM budget_line WHERE entity_id = ? AND period_id = ?",
        [(entity_id, pid) for pid in period_ids],
    )
    records = budget[["period_id", "account_code", "amount_local"]].to_dict("records")
    conn.executemany(
        """
        INSERT INTO budget_line(entity_id, period_id, account_code, amount_local)
        VALUES(:entity_id, :period_id, :account_code, :amount_local)
        """,
        [{"entity_id": entity_id, **r} for r in records],
    )
    return len(records)


def load(conn: sqlite3.Connection, entity_id: int, period_id: int) -> pd.DataFrame:
    """Return budget as a TB-shaped frame: account_code, account_desc, amount_local."""
    df = pd.read_sql_query(
        "SELECT account_code, amount_local FROM budget_line "
        "WHERE entity_id = ? AND period_id = ? ORDER BY account_code",
        conn,
        params=(entity_id, period_id),
    )
    df["account_desc"] = ""
    return df


def has_budget(conn: sqlite3.Connection, entity_id: int, period_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM budget_line WHERE entity_id = ? AND period_id = ? LIMIT 1",
        (entity_id, period_id),
    ).fetchone()
    return row is not None
