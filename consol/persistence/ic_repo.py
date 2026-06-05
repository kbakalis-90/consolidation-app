"""Repository for intercompany balances."""

from __future__ import annotations

import sqlite3

import pandas as pd


def replace_for_period(conn: sqlite3.Connection, period_id: int, ic: pd.DataFrame) -> int:
    """Replace all IC rows for a period.

    ``ic`` columns: entity_id, counterparty_id, ic_type, caption, amount_local.
    """
    conn.execute("DELETE FROM ic_balance WHERE period_id = ?", (period_id,))
    records = ic[["entity_id", "counterparty_id", "ic_type", "caption", "amount_local"]].to_dict(
        "records"
    )
    conn.executemany(
        """
        INSERT INTO ic_balance(period_id, entity_id, counterparty_id, ic_type, caption,
                               amount_local)
        VALUES(:period_id, :entity_id, :counterparty_id, :ic_type, :caption, :amount_local)
        """,
        [{"period_id": period_id, **r} for r in records],
    )
    return len(records)


def load_for_period(conn: sqlite3.Connection, period_id: int) -> pd.DataFrame:
    """Return IC rows joined to entity codes and the reporting entity's currency."""
    return pd.read_sql_query(
        """
        SELECT ic.entity_id, e.code AS entity_code, e.local_currency AS entity_ccy,
               ic.counterparty_id, c.code AS counterparty_code,
               ic.ic_type, ic.caption, ic.amount_local
        FROM ic_balance ic
        JOIN entity e ON e.entity_id = ic.entity_id
        JOIN entity c ON c.entity_id = ic.counterparty_id
        WHERE ic.period_id = ?
        ORDER BY e.code, c.code, ic.ic_type
        """,
        conn,
        params=(period_id,),
    )


def has_ic(conn: sqlite3.Connection, period_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM ic_balance WHERE period_id = ? LIMIT 1", (period_id,)
    ).fetchone()
    return row is not None
