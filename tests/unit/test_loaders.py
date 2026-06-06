"""Unit tests for ingestion loaders and the upload-time checks they feed."""

from __future__ import annotations

import pandas as pd
import pytest

from consol.ingestion.fx_loader import load_fx
from consol.ingestion.ic_loader import load_ic
from consol.ingestion.readers import IngestionError
from consol.ingestion.validators import normalize_caption
from consol.services import ingestion_service


def _csv(text: str) -> bytes:
    return text.encode("utf-8")


# --- load_fx --------------------------------------------------------------


def test_load_fx_rejects_zero_rate() -> None:
    src = _csv("currency,closing_rate,average_rate\nUSD,0,1.1\n")
    with pytest.raises(IngestionError, match="positive and non-zero"):
        load_fx(src, "fx.csv")


def test_load_fx_rejects_negative_rate() -> None:
    src = _csv("currency,closing_rate,average_rate\nUSD,1.1,-1.2\n")
    with pytest.raises(IngestionError, match="positive and non-zero"):
        load_fx(src, "fx.csv")


# --- ingest_fx: group-rate blocking vs missing-currency warning ------------


def test_ingest_fx_blocks_group_rate_not_one(conn) -> None:
    # Group currency (EUR) with a rate != 1.0 must reject the upload.
    src = _csv("currency,closing_rate,average_rate\nEUR,1.05,1.05\nUSD,1.1,1.1\n")
    res = ingestion_service.ingest_fx(conn, 2026, 1, src, "fx.csv")
    assert res.rows == 0
    assert res.has_errors
    assert any(c.check_id == "fx_group_rate" and not c.passed for c in res.checks)

    history = ingestion_service.upload_history(conn)
    assert (history["file_kind"] == "fx").any()
    assert (history["status"] == "rejected").any()


def test_ingest_fx_warns_on_missing_currency_but_persists(conn) -> None:
    # An entity needs USD but the file omits it: warn, still persist.
    ingestion_service.save_entity(conn, "US01", "Acme US", "USD")
    src = _csv("currency,closing_rate,average_rate\nEUR,1.0,1.0\n")
    res = ingestion_service.ingest_fx(conn, 2026, 1, src, "fx.csv")
    assert res.rows == 1
    assert not res.has_errors  # missing currency is only a warning
    present = next(c for c in res.checks if c.check_id == "fx_currencies_present")
    assert not present.passed
    assert "USD" in present.detail


def test_ingest_fx_group_rate_one_passes(conn) -> None:
    src = _csv("currency,closing_rate,average_rate\nEUR,1.0,1.0\nUSD,1.1,1.2\n")
    res = ingestion_service.ingest_fx(conn, 2026, 1, src, "fx.csv")
    assert res.rows == 2
    assert not res.has_errors


# --- caption normalization ------------------------------------------------


def test_normalize_caption_collapses_blanks() -> None:
    series = pd.Series(["Loan", None, float("nan"), "   ", "Loan"])
    out = normalize_caption(series)
    assert list(out) == ["Loan", "", "", "", "Loan"]
    assert out.nunique() == 2


def test_load_ic_normalizes_blank_caption() -> None:
    # Blank/NaN/whitespace captions should all collapse to "" so identical lines
    # collide instead of leaking distinct NULL keys to the DB.
    src = _csv(
        "entity_code,counterparty_code,ic_type,caption,amount_local\n"
        "A,B,receivable,,100\n"
        "A,B,receivable,   ,200\n"
    )
    ic = load_ic(src, "ic.csv")
    assert list(ic["caption"]) == ["", ""]


# --- ingest_ic ------------------------------------------------------------


def test_ingest_ic_blocks_duplicate(conn) -> None:
    ingestion_service.save_entity(conn, "A", "Alpha", "EUR")
    ingestion_service.save_entity(conn, "B", "Beta", "USD")
    src = _csv(
        "entity_code,counterparty_code,ic_type,caption,amount_local\n"
        "A,B,receivable,,100\n"
        "A,B,receivable,   ,200\n"  # same key after caption normalization
    )
    res = ingestion_service.ingest_ic(conn, 2026, 1, src, "ic.csv")
    assert res.rows == 0
    assert res.has_errors
    assert any(c.check_id == "ic_no_duplicates" and not c.passed for c in res.checks)

    history = ingestion_service.upload_history(conn)
    assert ((history["file_kind"] == "ic") & (history["status"] == "rejected")).any()


def test_ingest_ic_raises_on_unknown_entity(conn) -> None:
    ingestion_service.save_entity(conn, "A", "Alpha", "EUR")
    src = _csv("entity_code,counterparty_code,ic_type,caption,amount_local\nA,Z,receivable,,100\n")
    with pytest.raises(IngestionError, match="unknown entity code"):
        ingestion_service.ingest_ic(conn, 2026, 1, src, "ic.csv")


def test_ingest_ic_persists_clean_file(conn) -> None:
    ingestion_service.save_entity(conn, "A", "Alpha", "EUR")
    ingestion_service.save_entity(conn, "B", "Beta", "USD")
    src = _csv(
        "entity_code,counterparty_code,ic_type,caption,amount_local\n"
        "A,B,receivable,Loan,100\n"
        "A,B,payable,,50\n"
    )
    res = ingestion_service.ingest_ic(conn, 2026, 1, src, "ic.csv")
    assert res.rows == 2
    assert not res.has_errors


# --- friendly duplicate-key errors for cash / budget ----------------------


def test_ingest_cash_friendly_duplicate_error(conn) -> None:
    entity_id = ingestion_service.save_entity(conn, "A", "Alpha", "EUR")
    src = _csv(
        "cf_category,direct_line,flow_sign,amount_local\n"
        "operating,Receipts from customers,receipt,100\n"
        "operating,Receipts from customers,receipt,200\n"
    )
    with pytest.raises(IngestionError, match="duplicate"):
        ingestion_service.ingest_cash(conn, entity_id, 2026, 1, src, "cash.csv")


def test_ingest_budget_friendly_duplicate_error(conn) -> None:
    entity_id = ingestion_service.save_entity(conn, "A", "Alpha", "EUR")
    src = _csv("account_code,month,amount_local\n" "1000,1,100\n" "1000,1,200\n")
    with pytest.raises(IngestionError, match="duplicate"):
        ingestion_service.ingest_budget(conn, entity_id, 2026, src, "budget.csv")
