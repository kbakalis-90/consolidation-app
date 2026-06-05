"""Repository for cash-transaction data (direct method)."""

from __future__ import annotations

import sqlite3

import pandas as pd


def replace_for_entity_period(
    conn: sqlite3.Connection, entity_id: int, period_id: int, cash: pd.DataFrame
) -> int:
    """Replace cash transactions for one entity/period.

    Columns: cf_category, direct_line, flow_sign, amount_local.
    """
    conn.execute(
        "DELETE FROM cash_transaction WHERE entity_id = ? AND period_id = ?",
        (entity_id, period_id),
    )
    records = cash[["cf_category", "direct_line", "flow_sign", "amount_local"]].to_dict("records")
    conn.executemany(
        """
        INSERT INTO cash_transaction(entity_id, period_id, cf_category, direct_line,
                                     flow_sign, amount_local)
        VALUES(:entity_id, :period_id, :cf_category, :direct_line, :flow_sign, :amount_local)
        """,
        [{"entity_id": entity_id, "period_id": period_id, **r} for r in records],
    )
    return len(records)


def load(conn: sqlite3.Connection, entity_id: int, period_id: int) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT cf_category, direct_line, flow_sign, amount_local FROM cash_transaction "
        "WHERE entity_id = ? AND period_id = ? ORDER BY cf_category, direct_line",
        conn,
        params=(entity_id, period_id),
    )


def has_cash(conn: sqlite3.Connection, entity_id: int, period_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM cash_transaction WHERE entity_id = ? AND period_id = ? LIMIT 1",
        (entity_id, period_id),
    ).fetchone()
    return row is not None
