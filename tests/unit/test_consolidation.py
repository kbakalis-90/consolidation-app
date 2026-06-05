import pandas as pd

from consol.domain.consolidation import consolidate
from consol.domain.statements import build_statements
from consol.domain.translation import translate_bundle
from consol.models.entities import Entity


def _translate(tb, mapping, code, ccy="EUR"):
    entity = Entity(entity_id=hash(code) % 1000, code=code, name=code, local_currency=ccy)
    bundle = build_statements(tb, mapping, ccy)
    return translate_bundle(bundle, entity, 1.0, 1.0, "EUR", equity_historical_rate=1.0)


def _parent():
    tb = pd.DataFrame(
        {
            "account_code": ["1000", "1100", "3000", "4000"],
            "account_desc": ["Cash", "IC receivable", "Share capital", "Revenue"],
            "amount_local": [200.0, 50.0, -150.0, -100.0],
        }
    )
    mapping = pd.DataFrame(
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
        }
    )
    return _translate(tb, mapping, "P")


def _sub(payable: float):
    cash = 20.0 + payable  # keep the TB balanced: Cash = payable + share capital(20)
    tb = pd.DataFrame(
        {
            "account_code": ["1000", "2000", "3000"],
            "account_desc": ["Cash", "IC payable", "Share capital"],
            "amount_local": [cash, -payable, -20.0],
        }
    )
    mapping = pd.DataFrame(
        {
            "account_code": ["1000", "2000", "3000"],
            "statement": ["BS", "BS", "BS"],
            "caption": ["Cash and cash equivalents", "Trade payables", "Share capital"],
            "caption_order": [1, 2, 3],
            "normal_sign": ["debit", "credit", "credit"],
            "is_equity": [0, 0, 1],
            "is_cash": [1, 0, 0],
        }
    )
    return _translate(tb, mapping, "S")


def _ic(recv: float, pay: float):
    return pd.DataFrame(
        {
            "entity_id": [1, 2],
            "entity_code": ["P", "S"],
            "entity_ccy": ["EUR", "EUR"],
            "counterparty_id": [2, 1],
            "counterparty_code": ["S", "P"],
            "ic_type": ["receivable", "payable"],
            "caption": ["Trade receivables", "Trade payables"],
            "amount_local": [recv, pay],
        }
    )


def _amount(result_lines, caption):
    sel = result_lines.loc[result_lines["caption"] == caption, "amount"]
    return float(sel.sum())


def test_consolidation_matched_ic_fully_eliminated():
    entities = [_parent(), _sub(50.0)]
    result = consolidate(entities, _ic(50.0, 50.0), {"EUR": (1.0, 1.0)}, "EUR")

    bs = result.balance_sheet.lines
    assert _amount(bs, "Trade receivables") == 0.0  # fully eliminated
    assert _amount(bs, "Trade payables") == 0.0
    assert result.meta["total_assets"] == result.meta["total_liabilities_equity"]
    assert result.meta["total_assets"] == 270.0  # Cash 270 only

    recon = result.ic_reconciliation
    assert float(recon["bs_difference"].iloc[0]) == 0.0


def test_consolidation_balances_even_with_ic_mismatch():
    # Parent claims a 50 receivable; sub records only a 40 payable.
    entities = [_parent(), _sub(40.0)]
    result = consolidate(entities, _ic(50.0, 40.0), {"EUR": (1.0, 1.0)}, "EUR")

    # Matched 40 eliminated; 10 unmatched receivable remains and is flagged.
    bs = result.balance_sheet.lines
    assert _amount(bs, "Trade receivables") == 10.0
    assert _amount(bs, "Trade payables") == 0.0
    assert abs(result.meta["total_assets"] - result.meta["total_liabilities_equity"]) < 1e-9

    recon = result.ic_reconciliation
    assert float(recon["bs_difference"].iloc[0]) == 10.0


def test_consolidation_without_ic():
    entities = [_parent(), _sub(0.0)]
    result = consolidate(entities, pd.DataFrame(), {"EUR": (1.0, 1.0)}, "EUR")
    assert result.eliminations.empty
    assert result.ic_reconciliation.empty
    assert abs(result.meta["total_assets"] - result.meta["total_liabilities_equity"]) < 1e-9
