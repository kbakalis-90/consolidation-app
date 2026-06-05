import pandas as pd

from consol.domain.cashflow_indirect import SECTION_OPERATING, build_indirect_cashflow
from consol.domain.statements import build_statements, caption_attributes

_MAPPING = pd.DataFrame(
    {
        "account_code": ["1000", "1100", "2000", "3000", "4000", "5000"],
        "statement": ["BS", "BS", "BS", "BS", "PL", "PL"],
        "caption": [
            "Cash and cash equivalents",
            "Trade receivables",
            "Trade payables",
            "Share capital",
            "Revenue",
            "Operating expenses",
        ],
        "caption_order": [1, 2, 3, 4, 1, 2],
        "cf_category": [None, None, None, None, "operating", "operating"],
        "wc_class": [None, "AR", "AP", None, None, None],
        "normal_sign": ["debit", "debit", "credit", "credit", "credit", "debit"],
        "is_equity": [0, 0, 0, 1, 0, 0],
        "is_cash": [1, 0, 0, 0, 0, 0],
    }
)


def _bundle(cash, recv, pay, revenue, expense):
    tb = pd.DataFrame(
        {
            "account_code": ["1000", "1100", "2000", "3000", "4000", "5000"],
            "account_desc": ["Cash", "AR", "AP", "Capital", "Rev", "Exp"],
            "amount_local": [cash, recv, -pay, -100.0, -revenue, expense],
        }
    )
    return build_statements(tb, _MAPPING, "EUR")


def test_indirect_reconciles_to_cash_movement():
    prior = _bundle(cash=100.0, recv=50.0, pay=30.0, revenue=40.0, expense=20.0)
    current = _bundle(cash=140.0, recv=70.0, pay=50.0, revenue=100.0, expense=40.0)
    attrs = caption_attributes(_MAPPING)

    cf = build_indirect_cashflow(current.balance_sheet, prior.balance_sheet, attrs, "EUR")

    assert cf.opening_cash == 100.0
    assert cf.closing_cash == 140.0
    assert round(cf.net_change, 2) == 40.0
    assert round(cf.net_change - (cf.closing_cash - cf.opening_cash), 2) == 0.0


def test_indirect_buckets_result_and_working_capital():
    prior = _bundle(cash=100.0, recv=50.0, pay=30.0, revenue=40.0, expense=20.0)
    current = _bundle(cash=140.0, recv=70.0, pay=50.0, revenue=100.0, expense=40.0)
    attrs = caption_attributes(_MAPPING)
    cf = build_indirect_cashflow(current.balance_sheet, prior.balance_sheet, attrs, "EUR")

    op = cf.lines[cf.lines["section"] == SECTION_OPERATING]
    # Result movement 60-20 = 40; AR change -20; AP change +20 -> operating total 40.
    assert round(op["amount"].sum(), 2) == 40.0
    result_line = op[op["line"] == "Result for the period"]
    assert round(float(result_line["amount"].iloc[0]), 2) == 40.0
