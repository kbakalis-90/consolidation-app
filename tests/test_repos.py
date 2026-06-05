from consol.persistence import config_repo, entity_repo, mapping_repo, period_repo, tb_repo


def test_entity_upsert_and_lookup(conn):
    eid = entity_repo.upsert(conn, "UK01", "Acme UK", "GBP")
    conn.commit()
    assert entity_repo.get_by_code(conn, "UK01").entity_id == eid
    # Upsert again updates rather than duplicating.
    eid2 = entity_repo.upsert(conn, "UK01", "Acme UK Ltd", "GBP")
    assert eid == eid2
    assert entity_repo.get_by_id(conn, eid).name == "Acme UK Ltd"


def test_period_get_or_create_idempotent(conn):
    p1 = period_repo.get_or_create(conn, 2026, 1)
    p2 = period_repo.get_or_create(conn, 2026, 1)
    assert p1 == p2
    assert period_repo.find(conn, 2026, 1).label == "2026-01"


def test_mapping_replace(conn, sample_mapping):
    eid = entity_repo.upsert(conn, "UK01", "Acme UK", "GBP")
    n = mapping_repo.replace_for_entity(conn, eid, sample_mapping)
    assert n == 6
    assert mapping_repo.has_mapping(conn, eid)
    loaded = mapping_repo.load_for_entity(conn, eid)
    assert set(loaded["account_code"]) == set(sample_mapping["account_code"])


def test_tb_replace(conn, sample_tb):
    eid = entity_repo.upsert(conn, "UK01", "Acme UK", "GBP")
    pid = period_repo.get_or_create(conn, 2026, 1)
    n = tb_repo.replace_for_entity_period(conn, eid, pid, sample_tb)
    assert n == 6
    loaded = tb_repo.load(conn, eid, pid)
    assert abs(loaded["amount_local"].sum()) < 1e-9


def test_config_defaults(conn):
    assert config_repo.group_currency(conn) == "EUR"
    config_repo.set(conn, "group_currency", "USD")
    conn.commit()
    assert config_repo.group_currency(conn) == "USD"
