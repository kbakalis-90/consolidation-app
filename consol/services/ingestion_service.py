"""Validate and persist uploads. Sits between the UI and the repositories."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import BinaryIO

import pandas as pd

from consol.checks import ingestion_checks
from consol.ingestion.budget_loader import load_budget
from consol.ingestion.cash_loader import load_cash
from consol.ingestion.fx_loader import load_fx
from consol.ingestion.ic_loader import load_ic
from consol.ingestion.mapping_loader import load_mapping
from consol.ingestion.readers import IngestionError
from consol.ingestion.tb_loader import load_tb
from consol.models.results import CheckResult
from consol.persistence import (
    budget_repo,
    cash_repo,
    config_repo,
    db,
    entity_repo,
    fx_repo,
    ic_repo,
    mapping_repo,
    period_repo,
    tb_repo,
)


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


def ingest_fx(
    conn: sqlite3.Connection,
    year: int,
    month: int,
    source: bytes | BinaryIO,
    filename: str | None = None,
) -> IngestResult:
    rates = load_fx(source, filename)
    group_currency = config_repo.group_currency(conn)
    needed_currencies = {e.local_currency for e in entity_repo.list_all(conn)}

    checks = [
        ingestion_checks.fx_group_rate(rates, group_currency),
        ingestion_checks.fx_currencies_present(needed_currencies, rates, group_currency),
    ]
    # A wrong group rate mis-translates every entity, so block; a missing entity
    # currency is only a warning (not all entities may be uploaded yet).
    if any(c.is_blocking for c in checks):
        _log_upload(conn, "fx", None, None, filename, len(rates), "rejected")
        conn.commit()
        return IngestResult(rows=0, checks=checks)

    with db.transaction(conn):
        period_id = period_repo.get_or_create(conn, year, month)
        rows = fx_repo.replace_for_period(conn, period_id, rates)
        _log_upload(conn, "fx", None, period_id, filename, rows, "ok")
    return IngestResult(rows=rows, checks=checks)


def ingest_ic(
    conn: sqlite3.Connection,
    year: int,
    month: int,
    source: bytes | BinaryIO,
    filename: str | None = None,
) -> IngestResult:
    ic = load_ic(source, filename)

    # Resolve entity codes to ids; unknown codes are a hard error.
    codes = set(ic["entity_code"]) | set(ic["counterparty_code"])
    id_by_code = {
        c: (
            entity_repo.get_by_code(conn, c).entity_id if entity_repo.get_by_code(conn, c) else None
        )
        for c in codes
    }
    unknown = sorted(c for c, eid in id_by_code.items() if eid is None)
    if unknown:
        raise IngestionError(
            f"IC file references unknown entity code(s): {', '.join(unknown)}. "
            "Add them on the Setup page first."
        )
    ic["entity_id"] = ic["entity_code"].map(id_by_code)
    ic["counterparty_id"] = ic["counterparty_code"].map(id_by_code)

    # Duplicate lines on the composite key would double-count / collide with the
    # DB UNIQUE index, so block before persisting.
    checks = [ingestion_checks.ic_no_duplicates(ic)]
    if any(c.is_blocking for c in checks):
        _log_upload(conn, "ic", None, None, filename, len(ic), "rejected")
        conn.commit()
        return IngestResult(rows=0, checks=checks)

    with db.transaction(conn):
        period_id = period_repo.get_or_create(conn, year, month)
        try:
            rows = ic_repo.replace_for_period(conn, period_id, ic)
        except sqlite3.IntegrityError as exc:
            raise IngestionError(
                "IC file has duplicate intercompany lines on "
                "(entity, counterparty, type, caption)."
            ) from exc
        _log_upload(conn, "ic", None, period_id, filename, rows, "ok")
    return IngestResult(rows=rows, checks=checks)


def ingest_cash(
    conn: sqlite3.Connection,
    entity_id: int,
    year: int,
    month: int,
    source: bytes | BinaryIO,
    filename: str | None = None,
) -> IngestResult:
    cash = load_cash(source, filename)
    with db.transaction(conn):
        period_id = period_repo.get_or_create(conn, year, month)
        try:
            rows = cash_repo.replace_for_entity_period(conn, entity_id, period_id, cash)
        except sqlite3.IntegrityError as exc:
            raise IngestionError(
                "Cash file has duplicate (cf_category, direct_line) line(s)."
            ) from exc
        _log_upload(conn, "cash", entity_id, period_id, filename, rows, "ok")
    return IngestResult(rows=rows, checks=[])


def ingest_budget(
    conn: sqlite3.Connection,
    entity_id: int,
    year: int,
    source: bytes | BinaryIO,
    filename: str | None = None,
) -> IngestResult:
    budget = load_budget(source, filename)
    with db.transaction(conn):
        months = sorted(budget["month"].unique())
        period_ids = {m: period_repo.get_or_create(conn, year, int(m)) for m in months}
        budget = budget.copy()
        budget["period_id"] = budget["month"].map(period_ids)
        try:
            rows = budget_repo.replace_for_entity_periods(
                conn, entity_id, list(period_ids.values()), budget
            )
        except sqlite3.IntegrityError as exc:
            raise IngestionError(
                "Budget file has duplicate (month, account_code) line(s)."
            ) from exc
        _log_upload(conn, "budget", entity_id, None, filename, rows, "ok")
    return IngestResult(rows=rows, checks=[])


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
