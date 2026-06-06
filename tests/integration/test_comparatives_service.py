import pandas as pd

from consol.persistence import budget_repo, entity_repo, mapping_repo, period_repo, tb_repo
from consol.services import ingestion_service
from consol.services.comparatives_service import (
    build_consolidated_comparatives,
    build_entity_comparatives,
)

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


def test_entity_comparatives_prior_month_and_budget(conn):
    eid = entity_repo.upsert(conn, "E1", "Entity One", "EUR")
    mapping_repo.replace_for_entity(conn, eid, pd.DataFrame(_MAPPING))
    p0 = period_repo.get_or_create(conn, 2025, 12)
    p1 = period_repo.get_or_create(conn, 2026, 1)
    # Prior month and current actuals (each balanced: cash = capital + result).
    tb_repo.replace_for_entity_period(conn, eid, p0, _tb(100, 80, 40, 20))
    tb_repo.replace_for_entity_period(conn, eid, p1, _tb(140, 80, 100, 40))
    # Budget for Jan 2026 via the ingestion service (month column).
    budget_csv = (
        b"account_code,month,amount_local\n" b"1000,1,150\n3000,1,-80\n4000,1,-110\n5000,1,40\n"
    )
    ingestion_service.ingest_budget(conn, eid, 2026, budget_csv, "budget.csv")
    conn.commit()

    assert budget_repo.has_budget(conn, eid, p1)

    report = build_entity_comparatives(conn, eid, 2026, 1)
    assert report.available["Prior month"] is True
    assert report.available["Budget"] is True
    assert report.available["Prior year"] is False

    # P&L revenue: actual 100 vs prior month 40 vs budget 110.
    pl = report.pl_variance
    rev = pl[pl["caption"] == "Revenue"].iloc[0]
    assert rev["Actual"] == 100.0
    assert rev["Prior month"] == 40.0
    assert rev["Budget"] == 110.0
    assert rev["Budget Δ"] == -10.0


def test_consolidated_comparatives_prior_month(conn):
    # Single group-currency (EUR) entity needs no FX upload; build the group
    # prior-month comparison and confirm the consolidated variance ties out.
    eid = entity_repo.upsert(conn, "E1", "Entity One", "EUR")
    mapping_repo.replace_for_entity(conn, eid, pd.DataFrame(_MAPPING))
    p0 = period_repo.get_or_create(conn, 2025, 12)
    p1 = period_repo.get_or_create(conn, 2026, 1)
    tb_repo.replace_for_entity_period(conn, eid, p0, _tb(100, 80, 40, 20))
    tb_repo.replace_for_entity_period(conn, eid, p1, _tb(140, 80, 100, 40))
    conn.commit()

    report = build_consolidated_comparatives(conn, 2026, 1)
    assert report.title == "Consolidated group"
    assert report.currency == "EUR"
    assert report.available["Prior month"] is True
    assert report.available["Prior year"] is False

    rev = report.pl_variance[report.pl_variance["caption"] == "Revenue"].iloc[0]
    assert rev["Actual"] == 100.0
    assert rev["Prior month"] == 40.0
    assert rev["Prior month Δ"] == 60.0
