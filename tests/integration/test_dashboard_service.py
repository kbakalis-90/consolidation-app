import pandas as pd

from consol.persistence import entity_repo, mapping_repo, period_repo, tb_repo
from consol.services.dashboard_service import build_dashboard, collect_all_checks

_MAPPING = {
    "account_code": ["1000", "3000", "4000", "5000"],
    "statement": ["BS", "BS", "PL", "PL"],
    "caption": ["Cash and cash equivalents", "Share capital", "Revenue", "Operating expenses"],
    "caption_order": [1, 2, 1, 2],
    "normal_sign": ["debit", "credit", "credit", "debit"],
    "is_equity": [0, 1, 0, 0],
    "is_cash": [1, 0, 0, 0],
}


def _tb(cash, capital, revenue, expense):
    return pd.DataFrame(
        {
            "account_code": ["1000", "3000", "4000", "5000"],
            "account_desc": ["Cash", "Capital", "Rev", "Exp"],
            "amount_local": [cash, -capital, -revenue, expense],
        }
    )


def _seed(conn):
    eid = entity_repo.upsert(conn, "E1", "Entity One", "EUR")
    mapping_repo.replace_for_entity(conn, eid, pd.DataFrame(_MAPPING))
    p1 = period_repo.get_or_create(conn, 2026, 1)
    tb_repo.replace_for_entity_period(conn, eid, p1, _tb(140, 80, 100, 40))
    conn.commit()
    return eid


def test_dashboard_entity_kpis(conn):
    eid = _seed(conn)
    report = build_dashboard(conn, "entity", 2026, 1, eid)
    kpis = {k.name: k.value for k in report.kpis}
    assert kpis["Revenue"] == 100.0
    assert kpis["Net income"] == 60.0
    assert report.currency == "EUR"


def test_collect_all_checks_runs(conn):
    _seed(conn)
    checks = collect_all_checks(conn, 2026, 1)
    assert not checks.empty
    assert "tb_balances" in set(checks["check"])
    # The single-entity TB balances, so that check should pass.
    tb_row = checks[checks["check"] == "tb_balances"].iloc[0]
    assert bool(tb_row["passed"]) is True
