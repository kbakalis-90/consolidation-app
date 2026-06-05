"""Repository for per-entity account mappings."""

from __future__ import annotations

import sqlite3

import pandas as pd

_COLUMNS = [
    "account_code",
    "account_desc",
    "statement",
    "caption",
    "caption_order",
    "cf_category",
    "wc_class",
    "normal_sign",
    "is_equity",
    "is_cash",
]


def replace_for_entity(conn: sqlite3.Connection, entity_id: int, mapping: pd.DataFrame) -> int:
    """Replace the entire mapping for one entity. Returns rows written.

    ``mapping`` must contain the columns in :data:`_COLUMNS`.
    """
    conn.execute("DELETE FROM account_mapping WHERE entity_id = ?", (entity_id,))
    records = mapping[_COLUMNS].to_dict("records")
    conn.executemany(
        """
        INSERT INTO account_mapping(
            entity_id, account_code, account_desc, statement, caption, caption_order,
            cf_category, wc_class, normal_sign, is_equity, is_cash
        ) VALUES(
            :entity_id, :account_code, :account_desc, :statement, :caption, :caption_order,
            :cf_category, :wc_class, :normal_sign, :is_equity, :is_cash
        )
        """,
        [{"entity_id": entity_id, **r} for r in records],
    )
    return len(records)


def load_for_entity(conn: sqlite3.Connection, entity_id: int) -> pd.DataFrame:
    """Return the mapping for an entity as a DataFrame (empty if none)."""
    return pd.read_sql_query(
        "SELECT * FROM account_mapping WHERE entity_id = ? ORDER BY caption_order, account_code",
        conn,
        params=(entity_id,),
    )


def has_mapping(conn: sqlite3.Connection, entity_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM account_mapping WHERE entity_id = ? LIMIT 1", (entity_id,)
    ).fetchone()
    return row is not None
