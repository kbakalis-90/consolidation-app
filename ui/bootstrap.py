"""Shared helpers for the Streamlit UI."""

from __future__ import annotations

import sqlite3

from consol.persistence import db
from consol.persistence.migrations import apply_schema


def get_conn() -> sqlite3.Connection:
    """Open a connection and ensure the schema exists.

    A fresh connection per rerun keeps things simple for a local single-user
    tool and avoids cross-thread SQLite issues.
    """
    conn = db.connect()
    apply_schema(conn)
    return conn
