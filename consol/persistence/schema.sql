-- Source of truth for the SQLite schema. Idempotent (IF NOT EXISTS).
-- All monetary amounts are signed local-currency balances (debit +, credit -).

CREATE TABLE IF NOT EXISTS entity (
    entity_id        INTEGER PRIMARY KEY,
    code             TEXT NOT NULL UNIQUE,
    name             TEXT NOT NULL,
    local_currency   TEXT NOT NULL,
    is_active        INTEGER NOT NULL DEFAULT 1,
    parent_entity_id INTEGER REFERENCES entity(entity_id)
);

CREATE TABLE IF NOT EXISTS period (
    period_id   INTEGER PRIMARY KEY,
    year        INTEGER NOT NULL,
    month       INTEGER NOT NULL,
    label       TEXT NOT NULL,
    is_closed   INTEGER NOT NULL DEFAULT 0,
    UNIQUE(year, month)
);

CREATE TABLE IF NOT EXISTS config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Per-entity chart of accounts + mapping to standard statement captions.
CREATE TABLE IF NOT EXISTS account_mapping (
    mapping_id     INTEGER PRIMARY KEY,
    entity_id      INTEGER NOT NULL REFERENCES entity(entity_id),
    account_code   TEXT NOT NULL,
    account_desc   TEXT,
    statement      TEXT NOT NULL,              -- 'BS' | 'PL'
    caption        TEXT NOT NULL,
    caption_order  INTEGER NOT NULL,
    cf_category    TEXT,                        -- 'operating'|'investing'|'financing'|NULL
    wc_class       TEXT,                        -- 'AR'|'AP'|'inventory'|'other_wc'|NULL
    normal_sign    TEXT NOT NULL,              -- 'debit'|'credit'
    is_equity      INTEGER NOT NULL DEFAULT 0,
    is_cash        INTEGER NOT NULL DEFAULT 0,
    UNIQUE(entity_id, account_code)
);

CREATE TABLE IF NOT EXISTS tb_line (
    tb_line_id    INTEGER PRIMARY KEY,
    entity_id     INTEGER NOT NULL REFERENCES entity(entity_id),
    period_id     INTEGER NOT NULL REFERENCES period(period_id),
    account_code  TEXT NOT NULL,
    account_desc  TEXT,
    amount_local  REAL NOT NULL,
    UNIQUE(entity_id, period_id, account_code)
);

CREATE TABLE IF NOT EXISTS ic_balance (
    ic_id            INTEGER PRIMARY KEY,
    period_id        INTEGER NOT NULL REFERENCES period(period_id),
    entity_id        INTEGER NOT NULL REFERENCES entity(entity_id),
    counterparty_id  INTEGER NOT NULL REFERENCES entity(entity_id),
    ic_type          TEXT NOT NULL,
    caption          TEXT,
    amount_local     REAL NOT NULL,
    UNIQUE(period_id, entity_id, counterparty_id, ic_type, caption)
);

CREATE TABLE IF NOT EXISTS fx_rate (
    fx_id          INTEGER PRIMARY KEY,
    period_id      INTEGER NOT NULL REFERENCES period(period_id),
    currency       TEXT NOT NULL,
    closing_rate   REAL NOT NULL,
    average_rate   REAL NOT NULL,
    UNIQUE(period_id, currency)
);

CREATE TABLE IF NOT EXISTS cash_transaction (
    cash_id      INTEGER PRIMARY KEY,
    entity_id    INTEGER NOT NULL REFERENCES entity(entity_id),
    period_id    INTEGER NOT NULL REFERENCES period(period_id),
    cf_category  TEXT NOT NULL,
    direct_line  TEXT NOT NULL,
    flow_sign    TEXT NOT NULL,                -- 'receipt'|'payment'
    amount_local REAL NOT NULL,
    UNIQUE(entity_id, period_id, cf_category, direct_line)
);

CREATE TABLE IF NOT EXISTS budget_line (
    budget_id     INTEGER PRIMARY KEY,
    entity_id     INTEGER NOT NULL REFERENCES entity(entity_id),
    period_id     INTEGER NOT NULL REFERENCES period(period_id),
    account_code  TEXT NOT NULL,
    amount_local  REAL NOT NULL,
    UNIQUE(entity_id, period_id, account_code)
);

CREATE TABLE IF NOT EXISTS upload_log (
    upload_id   INTEGER PRIMARY KEY,
    file_kind   TEXT NOT NULL,
    entity_id   INTEGER REFERENCES entity(entity_id),
    period_id   INTEGER REFERENCES period(period_id),
    filename    TEXT,
    row_count   INTEGER,
    uploaded_at TEXT NOT NULL,
    status      TEXT NOT NULL
);
