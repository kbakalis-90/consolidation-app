"""Validate and persist uploads. Sits between the UI and the repositories."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import BinaryIO

import pandas as pd

from consol.checks import ingestion_checks
from consol.ingestion.mapping_loader import load_mapping
from consol.ingestion.tb_loader import load_tb
from consol.models.results import CheckResult
from consol.persistence import config_repo, db, entity_repo, mapping_repo, period_repo, tb_repo


@dataclass
class IngestResult:
    rows: int
    checks: list[CheckResult]

    @property
    def has_errors(self) -> bool:
        return any(c.is_blocking for c in self.checks)


def _log_upload(
    conn: sqlite3.Connection,
    file_kind: str,
    entity_id: int | None,
    period_id: int | None,
    filename: str | None,
    row_count: int,
    status: str,
) -> None:
    conn.execute(
        """
        INSERT INTO upload_log(file_kind, entity_id, period_id, filename, row_count,
                               uploaded_at, status)
        VALUES(?, ?, ?, ?, ?, ?, ?)
        """,
        (
            file_kind,
            entity_id,
            period_id,
            filename,
            row_count,
            datetime.now(UTC).isoformat(timespec="seconds"),
            status,
        ),
    )


def save_entity(conn: sqlite3.Connection, code: str, name: str, local_currency: str) -> int:
    with db.transaction(conn):
        return entity_repo.upsert(conn, code.strip(), name.strip(), local_currency.strip().upper())


def ingest_mapping(
    conn: sqlite3.Connection,
    entity_id: int,
    source: bytes | BinaryIO,
    filename: str | None = None,
) -> IngestResult:
    mapping = load_mapping(source, filename)
    checks = [ingestion_checks.no_duplicate_accounts(mapping, "mapping")]
    if any(c.is_blocking for c in checks):
        _log_upload(conn, "mapping", entity_id, None, filename, len(mapping), "rejected")
        conn.commit()
        return IngestResult(rows=0, checks=checks)
    with db.transaction(conn):
        rows = mapping_repo.replace_for_entity(conn, entity_id, mapping)
        _log_upload(conn, "mapping", entity_id, None, filename, rows, "ok")
    return IngestResult(rows=rows, checks=checks)


def ingest_tb(
    conn: sqlite3.Connection,
    entity_id: int,
    year: int,
    month: int,
    source: bytes | BinaryIO,
    filename: str | None = None,
) -> IngestResult:
    tb = load_tb(source, filename)
    tolerance = config_repo.balance_tolerance(conn)
    mapping = mapping_repo.load_for_entity(conn, entity_id)

    checks = [
        ingestion_checks.tb_balances(tb, tolerance),
        ingestion_checks.no_duplicate_accounts(tb, "trial balance"),
        ingestion_checks.all_accounts_mapped(tb, mapping),
    ]
    # Persist even with warnings; only block on duplicate codes (a data integrity issue).
    dup_failed = not checks[1].passed
    if dup_failed:
        _log_upload(conn, "tb", entity_id, None, filename, len(tb), "rejected")
        conn.commit()
        return IngestResult(rows=0, checks=checks)

    with db.transaction(conn):
        period_id = period_repo.get_or_create(conn, year, month)
        rows = tb_repo.replace_for_entity_period(conn, entity_id, period_id, tb)
        _log_upload(conn, "tb", entity_id, period_id, filename, rows, "ok")
    return IngestResult(rows=rows, checks=checks)


def upload_history(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT u.uploaded_at, u.file_kind, e.code AS entity, p.label AS period, "
        "u.filename, u.row_count, u.status "
        "FROM upload_log u "
        "LEFT JOIN entity e ON e.entity_id = u.entity_id "
        "LEFT JOIN period p ON p.period_id = u.period_id "
        "ORDER BY u.upload_id DESC",
        conn,
    )
