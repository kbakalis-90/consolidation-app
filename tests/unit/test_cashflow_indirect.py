import pandas as pd
import pytest

from consol.domain.cashflow_indirect import (
    SECTION_FINANCING,
    SECTION_INVESTING,
    SECTION_OPERATING,
    CtaInIndirectCashflowError,
    build_indirect_cashflow,
)
from consol.domain.statements import build_statements, caption_attributes
from consol.domain.translation import CAPTION_CTA

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


# Mapping that exercises the investing / financing / equity branches of _classify.
_CLASSIFY_MAPPING = pd.DataFrame(
    {
        "account_code": ["1000", "1500", "2500", "3000", "4000"],
        "statement": ["BS", "BS", "BS", "BS", "PL"],
        "caption": [
            "Cash and cash equivalents",
            "Property plant and equipment",
            "Borrowings",
            "Share capital",
            "Revenue",
        ],
        "caption_order": [1, 2, 3, 4, 1],
        "cf_category": [None, "investing", "financing", None, "operating"],
        "wc_class": [None, None, None, None, None],
        "normal_sign": ["debit", "debit", "credit", "credit", "credit"],
        "is_equity": [0, 0, 0, 1, 0],
        "is_cash": [1, 0, 0, 0, 0],
    }
)


def _classify_bundle(cash, ppe, borrowings, capital, revenue):
    tb = pd.DataFrame(
        {
            "account_code": ["1000", "1500", "2500", "3000", "4000"],
            "account_desc": ["Cash", "PPE", "Loan", "Capital", "Rev"],
            "amount_local": [cash, ppe, -borrowings, -capital, -revenue],
        }
    )
    return build_statements(tb, _CLASSIFY_MAPPING, "EUR")


def test_indirect_classifies_investing_financing_equity():
    prior = _classify_bundle(cash=100.0, ppe=200.0, borrowings=50.0, capital=200.0, revenue=0.0)
    current = _classify_bundle(cash=130.0, ppe=260.0, borrowings=80.0, capital=240.0, revenue=20.0)
    attrs = caption_attributes(_CLASSIFY_MAPPING)

    cf = build_indirect_cashflow(current.balance_sheet, prior.balance_sheet, attrs, "EUR")

    inv = cf.lines[cf.lines["section"] == SECTION_INVESTING]
    fin = cf.lines[cf.lines["section"] == SECTION_FINANCING]

    def _line(frame, label):
        return round(float(frame.loc[frame["line"] == label, "amount"].iloc[0]), 2)

    # PPE rose 60 (asset increase uses cash) -> -60 investing.
    assert _line(inv, "Change in Property plant and equipment") == -60.0
    # Borrowings rose 30 (cf_category financing) -> +30; share capital (equity) rose 40 -> +40.
    assert _line(fin, "Change in Borrowings") == 30.0
    assert _line(fin, "Change in Share capital") == 40.0
    # Whole statement still ties to the cash movement.
    assert round(cf.net_change - (cf.closing_cash - cf.opening_cash), 2) == 0.0


def test_indirect_rejects_cta_bearing_bundle():
    prior = _bundle(cash=100.0, recv=50.0, pay=30.0, revenue=40.0, expense=20.0)
    current = _bundle(cash=140.0, recv=70.0, pay=50.0, revenue=100.0, expense=40.0)
    attrs = caption_attributes(_MAPPING)

    # Inject a CTA line to mimic a translated bundle.
    poisoned = current.balance_sheet.lines.copy()
    poisoned = pd.concat(
        [
            poisoned,
            pd.DataFrame(
                [
                    {
                        "section": "Equity",
                        "caption": CAPTION_CTA,
                        "caption_order": 9500,
                        "amount": 5.0,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    current.balance_sheet.lines = poisoned

    with pytest.raises(CtaInIndirectCashflowError):
        build_indirect_cashflow(current.balance_sheet, prior.balance_sheet, attrs, "EUR")
