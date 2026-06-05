import pandas as pd

from consol.config import FX_DIRECTION_GROUP_PER_LOCAL
from consol.domain.sign_conventions import CAPTION_CURRENT_YEAR_RESULT
from consol.domain.statements import build_statements
from consol.domain.translation import CAPTION_CTA, translate_bundle
from consol.models.entities import Entity


def _sub_bundle():
    # USD sub: Cash 100 = Share capital 60 + Net income 40.
    tb = pd.DataFrame(
        {
            "account_code": ["1000", "3000", "4000"],
            "account_desc": ["Cash", "Share capital", "Revenue"],
            "amount_local": [100.0, -60.0, -40.0],
        }
    )
    mapping = pd.DataFrame(
        {
            "account_code": ["1000", "3000", "4000"],
            "statement": ["BS", "BS", "PL"],
            "caption": ["Cash and cash equivalents", "Share capital", "Revenue"],
            "caption_order": [1, 2, 1],
            "normal_sign": ["debit", "credit", "credit"],
            "is_equity": [0, 1, 0],
            "is_cash": [1, 0, 0],
        }
    )
    return build_statements(tb, mapping, "USD")


def test_worked_cta_example():
    """Group EUR; closing 1.25, average 1.10, historical 1.00 -> CTA = +21."""
    entity = Entity(entity_id=1, code="US01", name="US Sub", local_currency="USD")
    te = translate_bundle(
        _sub_bundle(),
        entity,
        closing_rate=1.25,
        average_rate=1.10,
        group_currency="EUR",
        direction=FX_DIRECTION_GROUP_PER_LOCAL,
        equity_historical_rate=1.00,
    )
    assert round(te.total_assets, 2) == 125.0
    assert round(te.net_income, 2) == 44.0
    assert round(te.cta, 2) == 21.0
    assert te.balances

    bs = te.balance_sheet.lines
    assert (
        round(float(bs.loc[bs["caption"] == "Cash and cash equivalents", "amount"].iloc[0]), 2)
        == 125.0
    )
    assert round(float(bs.loc[bs["caption"] == "Share capital", "amount"].iloc[0]), 2) == 60.0
    assert (
        round(float(bs.loc[bs["caption"] == CAPTION_CURRENT_YEAR_RESULT, "amount"].iloc[0]), 2)
        == 44.0
    )
    assert round(float(bs.loc[bs["caption"] == CAPTION_CTA, "amount"].iloc[0]), 2) == 21.0


def test_no_translation_when_historical_equals_closing():
    """If historical == closing == average, CTA is zero (no rate differences)."""
    entity = Entity(entity_id=1, code="US01", name="US Sub", local_currency="USD")
    te = translate_bundle(
        _sub_bundle(),
        entity,
        closing_rate=2.0,
        average_rate=2.0,
        group_currency="EUR",
        equity_historical_rate=2.0,
    )
    assert abs(te.cta) < 1e-9
    assert te.balances
