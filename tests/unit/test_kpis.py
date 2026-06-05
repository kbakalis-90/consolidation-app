import pandas as pd

from consol.domain.kpis import compute_kpis, revenue_growth
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
        "wc_class": [None, "AR", "AP", None, None, None],
        "normal_sign": ["debit", "debit", "credit", "credit", "credit", "debit"],
        "is_equity": [0, 0, 0, 1, 0, 0],
        "is_cash": [1, 0, 0, 0, 0, 0],
    }
)


def _bundle(cash, ar, pay, revenue, expense):
    tb = pd.DataFrame(
        {
            "account_code": ["1000", "1100", "2000", "3000", "4000", "5000"],
            "account_desc": ["Cash", "AR", "AP", "Capital", "Rev", "Exp"],
            "amount_local": [cash, ar, -pay, -100.0, -revenue, expense],
        }
    )
    return build_statements(tb, _MAPPING, "EUR")


def test_kpis_core_values():
    bundle = _bundle(cash=140.0, ar=70.0, pay=50.0, revenue=100.0, expense=40.0)
    attrs = caption_attributes(_MAPPING)
    kpis = {
        k.name: k.value for k in compute_kpis(bundle.balance_sheet, bundle.profit_and_loss, attrs)
    }

    assert kpis["Revenue"] == 100.0
    assert kpis["Operating expenses"] == 40.0
    assert kpis["Net income"] == 60.0
    assert round(kpis["Net margin"], 1) == 60.0
    # Total assets = cash 140 + AR 70 = 210.
    assert kpis["Total assets"] == 210.0
    assert kpis["Cash & equivalents"] == 140.0
    # Working capital = AR 70 - AP 50 = 20.
    assert kpis["Working capital"] == 20.0


def test_revenue_growth():
    prior = _bundle(100.0, 50.0, 30.0, 40.0, 20.0)
    current = _bundle(140.0, 70.0, 50.0, 100.0, 40.0)
    g = revenue_growth(current.profit_and_loss, prior.profit_and_loss)
    assert round(g, 1) == 150.0  # 40 -> 100 is +150%
