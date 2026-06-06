"""Shared helpers for the Streamlit UI."""

from __future__ import annotations

import sqlite3

import streamlit as st

from consol.persistence import db
from consol.persistence.migrations import apply_schema


@st.cache_resource
def get_conn() -> sqlite3.Connection:
    """Return the process-wide SQLite connection, creating it once.

    A single connection per process keeps things simple for a local single-user
    tool and avoids cross-thread SQLite issues. ``@st.cache_resource`` caches the
    connection across reruns and sessions, so ``apply_schema`` runs only once
    (on first call) rather than on every Streamlit rerun.
    """
    conn = db.connect()
    apply_schema(conn)
    return conn
