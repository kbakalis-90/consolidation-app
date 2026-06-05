import pandas as pd

from consol.persistence import entity_repo, fx_repo, ic_repo, mapping_repo, period_repo, tb_repo
from consol.services.consolidation_service import build_consolidation


def _seed_entity(conn, code, ccy, tb_rows, mapping_rows):
    eid = entity_repo.upsert(conn, code, code, ccy)
    mapping_repo.replace_for_entity(conn, eid, pd.DataFrame(mapping_rows))
    pid = period_repo.get_or_create(conn, 2026, 1)
    tb_repo.replace_for_entity_period(conn, eid, pid, pd.DataFrame(tb_rows))
    conn.commit()
    return eid, pid


_BASE_MAPPING = {
    "caption_order": [1, 2, 3, 4],
    "cf_category": [None, None, None, None],
    "wc_class": [None, None, None, None],
    "is_cash": [1, 0, 0, 0],
}


def test_two_entity_consolidation_balances_and_reconciles(conn):
    # Parent in group currency (EUR).
    _seed_entity(
        conn,
        "P",
        "EUR",
        {
            "account_code": ["1000", "1100", "3000", "4000"],
            "account_desc": ["Cash", "IC recv", "Capital", "Revenue"],
            "amount_local": [200.0, 50.0, -150.0, -100.0],
        },
        {
            "account_code": ["1000", "1100", "3000", "4000"],
            "statement": ["BS", "BS", "BS", "PL"],
            "caption": [
                "Cash and cash equivalents",
                "Trade receivables",
                "Share capital",
                "Revenue",
            ],
            "caption_order": [1, 2, 3, 1],
            "normal_sign": ["debit", "debit", "credit", "credit"],
            "is_equity": [0, 0, 1, 0],
            "is_cash": [1, 0, 0, 0],
        },
    )
    # Subsidiary in USD.
    _seed_entity(
        conn,
        "S",
        "USD",
        {
            "account_code": ["1000", "2000", "3000"],
            "account_desc": ["Cash", "IC pay", "Capital"],
            "amount_local": [60.0, -40.0, -20.0],
        },
        {
            "account_code": ["1000", "2000", "3000"],
            "statement": ["BS", "BS", "BS"],
            "caption": ["Cash and cash equivalents", "Trade payables", "Share capital"],
            "caption_order": [1, 2, 3],
            "normal_sign": ["debit", "credit", "credit"],
            "is_equity": [0, 0, 1],
            "is_cash": [1, 0, 0],
        },
    )

    pid = period_repo.get_or_create(conn, 2026, 1)
    fx_repo.replace_for_period(
        conn,
        pid,
        pd.DataFrame(
            {"currency": ["EUR", "USD"], "closing_rate": [1.0, 1.25], "average_rate": [1.0, 1.10]}
        ),
    )
    p = entity_repo.get_by_code(conn, "P")
    s = entity_repo.get_by_code(conn, "S")
    ic_repo.replace_for_period(
        conn,
        pid,
        pd.DataFrame(
            {
                "entity_id": [p.entity_id, s.entity_id],
                "counterparty_id": [s.entity_id, p.entity_id],
                "ic_type": ["receivable", "payable"],
                "caption": ["Trade receivables", "Trade payables"],
                "amount_local": [50.0, 40.0],
            }
        ),
    )
    conn.commit()

    report = build_consolidation(conn, 2026, 1)
    assert report.result is not None
    ta = report.result.meta["total_assets"]
    tle = report.result.meta["total_liabilities_equity"]
    assert abs(ta - tle) < 1e-6

    # 50 EUR receivable vs 40 USD * 1.25 = 50 EUR payable -> reconciles.
    recon = report.result.ic_reconciliation
    assert abs(float(recon["bs_difference"].iloc[0])) < 1e-6

    # No blocking errors.
    assert not report.checks.has_blocking_errors


def test_consolidation_blocks_on_missing_fx(conn):
    _seed_entity(
        conn,
        "S",
        "USD",
        {
            "account_code": ["1000", "3000"],
            "account_desc": ["Cash", "Capital"],
            "amount_local": [100.0, -100.0],
        },
        {
            "account_code": ["1000", "3000"],
            "statement": ["BS", "BS"],
            "caption": ["Cash and cash equivalents", "Share capital"],
            "caption_order": [1, 2],
            "normal_sign": ["debit", "credit"],
            "is_equity": [0, 1],
            "is_cash": [1, 0],
        },
    )
    # No FX uploaded for USD.
    report = build_consolidation(conn, 2026, 1)
    fx_checks = [c for c in report.checks.results if c.check_id == "fx_completeness"]
    assert fx_checks and not fx_checks[0].passed
