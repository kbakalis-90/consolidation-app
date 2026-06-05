"""Repository for entities."""

from __future__ import annotations

import sqlite3

from consol.models.entities import Entity


def _row_to_entity(row: sqlite3.Row) -> Entity:
    return Entity(
        entity_id=row["entity_id"],
        code=row["code"],
        name=row["name"],
        local_currency=row["local_currency"],
        is_active=bool(row["is_active"]),
        parent_entity_id=row["parent_entity_id"],
    )


def upsert(
    conn: sqlite3.Connection,
    code: str,
    name: str,
    local_currency: str,
    is_active: bool = True,
    parent_entity_id: int | None = None,
) -> int:
    """Insert or update an entity by its unique code. Returns the entity_id."""
    conn.execute(
        """
        INSERT INTO entity(code, name, local_currency, is_active, parent_entity_id)
        VALUES(?, ?, ?, ?, ?)
        ON CONFLICT(code) DO UPDATE SET
            name = excluded.name,
            local_currency = excluded.local_currency,
            is_active = excluded.is_active,
            parent_entity_id = excluded.parent_entity_id
        """,
        (code, name, local_currency, int(is_active), parent_entity_id),
    )
    row = conn.execute("SELECT entity_id FROM entity WHERE code = ?", (code,)).fetchone()
    return int(row["entity_id"])


def get_by_id(conn: sqlite3.Connection, entity_id: int) -> Entity | None:
    row = conn.execute("SELECT * FROM entity WHERE entity_id = ?", (entity_id,)).fetchone()
    return _row_to_entity(row) if row else None


def get_by_code(conn: sqlite3.Connection, code: str) -> Entity | None:
    row = conn.execute("SELECT * FROM entity WHERE code = ?", (code,)).fetchone()
    return _row_to_entity(row) if row else None


def list_all(conn: sqlite3.Connection, active_only: bool = False) -> list[Entity]:
    sql = "SELECT * FROM entity"
    if active_only:
        sql += " WHERE is_active = 1"
    sql += " ORDER BY code"
    return [_row_to_entity(r) for r in conn.execute(sql).fetchall()]
