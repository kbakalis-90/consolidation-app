import pandas as pd

from consol.checks import cashflow_checks
from consol.domain.cashflow_direct import build_direct_cashflow
from consol.domain.cashflow_indirect import SECTION_INVESTING, SECTION_OPERATING


def _cash():
    return pd.DataFrame(
        {
            "cf_category": ["operating", "operating", "investing"],
            "direct_line": ["Receipts from customers", "Payments to suppliers", "Purchase of PPE"],
            "flow_sign": ["receipt", "payment", "payment"],
            "amount_local": [190.0, 150.0, 0.0],
        }
    )


def test_direct_net_change_and_sections():
    cf = build_direct_cashflow(_cash(), "EUR", opening_cash=100.0, closing_cash=140.0)
    assert round(cf.net_change, 2) == 40.0
    assert round(cf.section_total(SECTION_OPERATING), 2) == 40.0
    assert SECTION_INVESTING in set(cf.lines["section"])


def test_direct_ties_to_cash_check():
    cf = build_direct_cashflow(_cash(), "EUR", opening_cash=100.0, closing_cash=140.0)
    assert cashflow_checks.direct_ties_to_cash(cf, 0.01).passed

    bad = build_direct_cashflow(_cash(), "EUR", opening_cash=100.0, closing_cash=200.0)
    assert not cashflow_checks.direct_ties_to_cash(bad, 0.01).passed
