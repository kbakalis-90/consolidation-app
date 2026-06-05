"""Connection factory and transaction helper.

This module is the single stateful seam of the application. To move to a
multi-user deployment, swap this for a pooled connection against another
engine; nothing in ``domain`` or ``checks`` needs to change.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from consol.config import SETTINGS


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Open a connection with sane PRAGMAs and row access by name.

    Pass ``":memory:"`` for tests.
    """
    target = str(db_path) if db_path is not None else str(SETTINGS.db_path)
    if target != ":memory:":
        Path(target).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Context manager that commits on success and rolls back on error."""
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
