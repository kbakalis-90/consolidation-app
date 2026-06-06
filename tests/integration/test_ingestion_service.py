import pytest

from consol.ingestion.readers import IngestionError
from consol.services import ingestion_service
from consol.services.reporting_service import build_entity_report


def test_full_ingest_and_report(conn, tb_csv_bytes, mapping_csv_bytes):
    entity_id = ingestion_service.save_entity(conn, "UK01", "Acme UK", "GBP")

    map_res = ingestion_service.ingest_mapping(
        conn, entity_id, mapping_csv_bytes, "entity_A_mapping.csv"
    )
    assert map_res.rows == 6
    assert not map_res.has_errors

    tb_res = ingestion_service.ingest_tb(
        conn, entity_id, 2026, 1, tb_csv_bytes, "entity_A_tb_2026-01.csv"
    )
    assert tb_res.rows == 6
    assert not tb_res.has_errors
    # tb_balances, no-dup, all-mapped should all pass.
    assert all(c.passed for c in tb_res.checks)

    report = build_entity_report(conn, entity_id, 2026, 1)
    assert report.bundle.balances
    assert report.bundle.net_income == 200.0
    assert report.checks.all_passed


def test_reupload_replaces_tb(conn, tb_csv_bytes, mapping_csv_bytes):
    entity_id = ingestion_service.save_entity(conn, "UK01", "Acme UK", "GBP")
    ingestion_service.ingest_mapping(conn, entity_id, mapping_csv_bytes, "m.csv")
    ingestion_service.ingest_tb(conn, entity_id, 2026, 1, tb_csv_bytes, "tb.csv")
    ingestion_service.ingest_tb(conn, entity_id, 2026, 1, tb_csv_bytes, "tb.csv")

    from consol.persistence import period_repo, tb_repo

    period_id = period_repo.get_or_create(conn, 2026, 1)
    tb = tb_repo.load(conn, entity_id, period_id)
    assert len(tb) == 6  # not duplicated


def test_ingest_fx_rejected_does_not_persist(conn):
    src = b"currency,closing_rate,average_rate\nEUR,1.05,1.05\nUSD,1.1,1.1\n"
    res = ingestion_service.ingest_fx(conn, 2026, 1, src, "fx.csv")
    assert res.rows == 0
    assert res.has_errors

    from consol.persistence import fx_repo, period_repo

    period_id = period_repo.get_or_create(conn, 2026, 1)
    # Nothing should have been written for the rejected upload.
    assert fx_repo.load_for_period(conn, period_id).empty


def test_ingest_ic_duplicate_rejected_does_not_persist(conn):
    ingestion_service.save_entity(conn, "A", "Alpha", "EUR")
    ingestion_service.save_entity(conn, "B", "Beta", "USD")
    src = (
        b"entity_code,counterparty_code,ic_type,caption,amount_local\n"
        b"A,B,receivable,,100\nA,B,receivable,   ,200\n"
    )
    res = ingestion_service.ingest_ic(conn, 2026, 1, src, "ic.csv")
    assert res.rows == 0
    assert res.has_errors

    from consol.persistence import ic_repo, period_repo

    period_id = period_repo.get_or_create(conn, 2026, 1)
    assert not ic_repo.has_ic(conn, period_id)


def test_reupload_replaces_fx(conn):
    from consol.persistence import fx_repo, period_repo

    first = b"currency,closing_rate,average_rate\nEUR,1.0,1.0\nUSD,1.10,1.05\n"
    second = b"currency,closing_rate,average_rate\nEUR,1.0,1.0\nUSD,1.25,1.20\n"
    assert not ingestion_service.ingest_fx(conn, 2026, 1, first, "fx.csv").has_errors
    assert not ingestion_service.ingest_fx(conn, 2026, 1, second, "fx.csv").has_errors

    period_id = period_repo.get_or_create(conn, 2026, 1)
    rates = fx_repo.load_for_period(conn, period_id)
    assert len(rates) == 2  # replaced, not appended
    usd = rates.loc[rates["currency"] == "USD"].iloc[0]
    assert usd["closing_rate"] == 1.25  # latest upload wins


def test_ingest_budget_duplicate_raises_friendly(conn):
    entity_id = ingestion_service.save_entity(conn, "A", "Alpha", "EUR")
    src = b"account_code,month,amount_local\n1000,1,100\n1000,1,200\n"
    with pytest.raises(IngestionError, match="duplicate"):
        ingestion_service.ingest_budget(conn, entity_id, 2026, src, "budget.csv")
