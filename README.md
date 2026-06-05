# Consolidation & Reporting Tool

A monthly financial reporting tool that consolidates the financial statements of multiple legal
entities — each reporting in its own local currency — into a single group reporting currency.
Built with Python, Streamlit and pandas; data persisted in a local SQLite database.

## Status

Delivered in phases (see the implementation plan). **Phase 1 is complete:** project foundation,
SQLite data model, file ingestion (trial balance + account mapping) with validation, and
single-entity Balance Sheet & P&L in local currency with built-in accuracy checks.

Upcoming: FX translation + consolidation + CTA (Phase 2), cash flow statements (Phase 3),
comparatives & variance (Phase 4), KPI dashboard & full check panel (Phase 5).

## Architecture

Strictly layered so the accounting engine stays pure and testable, and the tool can later be
deployed / made multi-user without rewriting the core:

```
ui (Streamlit)  →  services (orchestration)  →  domain (pure pandas/accounting)
                          ↓
                   persistence (SQLite repositories)
```

* `consol/` — the Streamlit-free core package (domain, checks, ingestion, persistence, services).
* `ui/` — Streamlit pages and presentation components.
* `tests/` — pytest unit + integration tests with fixtures.
* `scripts/generate_templates.py` — writes blank input templates to `data/templates/`.

Sign convention: amounts are stored canonically as **debit positive, credit negative**;
statements re-sign for natural presentation.

## Setup

```bash
pip install -e ".[dev]"
python -m scripts.generate_templates   # optional: blank input templates
```

## Run the app

```bash
streamlit run app.py
```

Then: **Setup** (group currency + entities) → **Upload** (account mapping, then trial balance) →
**Entity Statements** (Balance Sheet & P&L with checks).

## Input files (Phase 1)

* **Account mapping** (per entity): `account_code, statement (BS/PL), caption, normal_sign
  (debit/credit)` required; `account_desc, caption_order, cf_category, wc_class, is_equity,
  is_cash` optional.
* **Trial balance** (per entity/period): `account_code` plus either `debit`/`credit` columns or a
  signed `amount` column; optional `account_desc`.

## Tests

```bash
pytest            # run all tests
ruff check .      # lint
black .           # format
```
