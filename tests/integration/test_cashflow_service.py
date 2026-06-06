import pandas as pd

from consol.persistence import (
    cash_repo,
    entity_repo,
    fx_repo,
    mapping_repo,
    period_repo,
    tb_repo,
)
from consol.services.cashflow_service import (
    build_consolidated_cashflow,
    build_entity_cashflow,
)

_MAPPING = {
    "account_code": ["1000", "1100", "2000", "3000", "4000", "5000"],
    "statement": ["BS", "BS", "BS", "BS", "PL", "PL"],
    "caption": [
        "Cash and cash equivalents",
        "Trade receivables",
        "Trade payables",
        "Share capital",
        "Revenue",
        "Operating expenses",
    ],
    "caption_order": [1, 2, 3, 4, 1, 2],
    "cf_category": [None, None, None, None, "operating", "operating"],
    "wc_class": [None, "AR", "AP", None, None, None],
    "normal_sign": ["debit", "debit", "credit", "credit", "credit", "debit"],
    "is_equity": [0, 0, 0, 1, 0, 0],
    "is_cash": [1, 0, 0, 0, 0, 0],
}


def _tb(cash, recv, pay, revenue, expense):
    return pd.DataFrame(
        {
            "account_code": ["1000", "1100", "2000", "3000", "4000", "5000"],
            "account_desc": ["Cash", "AR", "AP", "Capital", "Rev", "Exp"],
            "amount_local": [cash, recv, -pay, -100.0, -revenue, expense],
        }
    )


def _seed(conn):
    eid = entity_repo.upsert(conn, "E1", "Entity One", "EUR")
    mapping_repo.replace_for_entity(conn, eid, pd.DataFrame(_MAPPING))
    p0 = period_repo.get_or_create(conn, 2025, 12)
    p1 = period_repo.get_or_create(conn, 2026, 1)
    tb_repo.replace_for_entity_period(conn, eid, p0, _tb(100, 50, 30, 40, 20))
    tb_repo.replace_for_entity_period(conn, eid, p1, _tb(140, 70, 50, 100, 40))
    conn.commit()
    return eid, p1


def test_entity_cashflow_indirect_reconciles(conn):
    _seed(conn)
    report = build_entity_cashflow(conn, entity_repo.get_by_code(conn, "E1").entity_id, 2026, 1)
    assert report.has_prior
    assert report.indirect is not None
    assert round(report.indirect.net_change, 2) == 40.0
    assert not report.checks.has_blocking_errors


def test_entity_cashflow_both_methods_agree(conn):
    eid, p1 = _seed(conn)
    cash_repo.replace_for_entity_period(
        conn,
        eid,
        p1,
        pd.DataFrame(
            {
                "cf_category": ["operating", "operating"],
                "direct_line": ["Receipts from customers", "Payments to suppliers"],
                "flow_sign": ["receipt", "payment"],
                "amount_local": [190.0, 150.0],
            }
        ),
    )
    conn.commit()
    report = build_entity_cashflow(conn, eid, 2026, 1)
    assert report.direct is not None
    assert round(report.direct.net_change, 2) == 40.0
    # Indirect and direct both 40 -> agreement check passes; no blocking errors.
    assert not report.checks.has_blocking_errors


def _seed_fx_entity(conn, code, ccy):
    eid = entity_repo.upsert(conn, code, code, ccy)
    mapping_repo.replace_for_entity(conn, eid, pd.DataFrame(_MAPPING))
    p0 = period_repo.get_or_create(conn, 2025, 12)
    p1 = period_repo.get_or_create(conn, 2026, 1)
    tb_repo.replace_for_entity_period(conn, eid, p0, _tb(100, 50, 30, 40, 20))
    tb_repo.replace_for_entity_period(conn, eid, p1, _tb(140, 70, 50, 100, 40))
    return eid, p0, p1


def test_consolidated_cashflow_runs_fx_and_tie_checks(conn):
    _seed_fx_entity(conn, "US", "USD")
    p0 = period_repo.find(conn, 2025, 12)
    p1 = period_repo.find(conn, 2026, 1)
    fx_repo.replace_for_period(
        conn,
        p1.period_id,
        pd.DataFrame(
            {"currency": ["USD", "EUR"], "closing_rate": [1.2, 1.0], "average_rate": [1.1, 1.0]}
        ),
    )
    fx_repo.replace_for_period(
        conn,
        p0.period_id,
        pd.DataFrame(
            {"currency": ["USD", "EUR"], "closing_rate": [1.0, 1.0], "average_rate": [1.0, 1.0]}
        ),
    )
    conn.commit()

    report = build_consolidated_cashflow(conn, 2026, 1)
    ids = {c.check_id for c in report.checks.results}
    assert "consolidated_indirect_ties_to_cash" in ids
    assert "fx_completeness" in ids
    assert not report.checks.has_blocking_errors


def test_consolidated_cashflow_blocks_on_missing_fx_rate(conn):
    _seed_fx_entity(conn, "US", "USD")
    p0 = period_repo.find(conn, 2025, 12)
    p1 = period_repo.find(conn, 2026, 1)
    # Only EUR present for the current period; USD silently falls back to (1, 1).
    fx_repo.replace_for_period(
        conn,
        p1.period_id,
        pd.DataFrame({"currency": ["EUR"], "closing_rate": [1.0], "average_rate": [1.0]}),
    )
    fx_repo.replace_for_period(
        conn,
        p0.period_id,
        pd.DataFrame({"currency": ["EUR"], "closing_rate": [1.0], "average_rate": [1.0]}),
    )
    conn.commit()

    report = build_consolidated_cashflow(conn, 2026, 1)
    fx = [c for c in report.checks.results if c.check_id == "fx_completeness"]
    assert fx and not fx[0].passed
    assert report.checks.has_blocking_errors


def test_entity_cashflow_blocks_without_prior(conn):
    eid = entity_repo.upsert(conn, "E2", "Entity Two", "EUR")
    mapping_repo.replace_for_entity(conn, eid, pd.DataFrame(_MAPPING))
    p1 = period_repo.get_or_create(conn, 2026, 1)
    tb_repo.replace_for_entity_period(conn, eid, p1, _tb(140, 70, 50, 100, 40))
    conn.commit()
    report = build_entity_cashflow(conn, eid, 2026, 1)
    assert not report.has_prior
    assert report.indirect is None
    prior_checks = [c for c in report.checks.results if c.check_id == "prior_period_present"]
    assert prior_checks and not prior_checks[0].passed
