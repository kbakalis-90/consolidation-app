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
