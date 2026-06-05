"""Repository for trial-balance lines."""

from __future__ import annotations

import sqlite3

import pandas as pd


def replace_for_entity_period(
    conn: sqlite3.Connection, entity_id: int, period_id: int, tb: pd.DataFrame
) -> int:
    """Replace the TB for one entity/period. Returns rows written.

    ``tb`` must contain columns ``account_code, account_desc, amount_local``.
    """
    conn.execute(
        "DELETE FROM tb_line WHERE entity_id = ? AND period_id = ?",
        (entity_id, period_id),
    )
    records = tb[["account_code", "account_desc", "amount_local"]].to_dict("records")
    conn.executemany(
        """
        INSERT INTO tb_line(entity_id, period_id, account_code, account_desc, amount_local)
        VALUES(:entity_id, :period_id, :account_code, :account_desc, :amount_local)
        """,
        [{"entity_id": entity_id, "period_id": period_id, **r} for r in records],
    )
    return len(records)


def load(conn: sqlite3.Connection, entity_id: int, period_id: int) -> pd.DataFrame:
    """Return TB lines for an entity/period (empty DataFrame if none)."""
    return pd.read_sql_query(
        "SELECT account_code, account_desc, amount_local FROM tb_line "
        "WHERE entity_id = ? AND period_id = ? ORDER BY account_code",
        conn,
        params=(entity_id, period_id),
    )


def has_tb(conn: sqlite3.Connection, entity_id: int, period_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM tb_line WHERE entity_id = ? AND period_id = ? LIMIT 1",
        (entity_id, period_id),
    ).fetchone()
    return row is not None
