# Consolidation & Reporting Tool

A monthly financial reporting tool that consolidates the financial statements of multiple legal
entities — each reporting in its own local currency — into a single group reporting currency.
Built with Python, Streamlit and pandas; data persisted in a local SQLite database.

## Status

Delivered in phases (see the implementation plan).

* **Phase 1 (complete):** project foundation, SQLite data model, ingestion (trial balance +
  account mapping) with validation, single-entity Balance Sheet & P&L in local currency, checks.
* **Phase 2 (complete):** FX-rate upload, current-rate translation (IAS 21) with CTA,
  multi-entity consolidation, intercompany elimination and two-sided reconciliation.
* **Phase 3 (complete):** cash flow statements — indirect (from balance-sheet movements) and
  direct (from uploaded cash transactions), per entity and consolidated, both reconciling to the
  change in cash, with an explicit FX-effect line on the consolidated view.
* **Phase 4 (complete):** annual budget upload and variance — actual vs prior month, prior year
  (same month) and budget — across the Balance Sheet and P&L, for entities and the group.

Upcoming: KPI dashboard & full check panel (Phase 5).

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

## Input files

* **Account mapping** (per entity): `account_code, statement (BS/PL), caption, normal_sign
  (debit/credit)` required; `account_desc, caption_order, cf_category, wc_class, is_equity,
  is_cash` optional.
* **Trial balance** (per entity/period): `account_code` plus either `debit`/`credit` columns or a
  signed `amount` column; optional `account_desc`.
* **FX rates** (per period): `currency, closing_rate, average_rate`. The group currency must have
  a rate of 1.0. Direction is set by config (`group_per_local` by default).
* **Intercompany** (per period): `entity_code, counterparty_code, ic_type
  (receivable/payable/income/expense), amount_local`; optional `caption`.
* **Cash transactions** (per entity/period, direct method): `cf_category
  (operating/investing/financing), direct_line, flow_sign (receipt/payment), amount_local`.
* **Budget** (per entity, annual, TB-shaped): `account_code, month (1-12), amount_local` (signed);
  optional `account_desc`.

## Translation & consolidation (Phase 2)

Entities are translated to the group currency using the current-rate method: balance-sheet items
at the closing rate, P&L at the average rate, non-result equity at a historical rate (the prior
period's closing rate as an opening proxy). The residual is booked to a **Cumulative Translation
Adjustment (CTA)** in equity. On consolidation, intercompany receivables/payables and
income/expense are eliminated by their matched amount (keeping the balance sheet balanced), and a
two-sided reconciliation flags any unmatched difference.

## Tests

```bash
pytest            # run all tests
ruff check .      # lint
black .           # format
```
