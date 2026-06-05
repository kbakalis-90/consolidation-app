import pandas as pd

from consol.domain.sign_conventions import income_positive, natural_amount


def test_natural_amount_debit_normal_positive_when_debit():
    canonical = pd.Series([500.0, -100.0])
    signs = pd.Series(["debit", "debit"])
    out = natural_amount(canonical, signs)
    assert list(out) == [500.0, -100.0]


def test_natural_amount_credit_normal_flips_sign():
    canonical = pd.Series([-400.0, 200.0])
    signs = pd.Series(["credit", "credit"])
    out = natural_amount(canonical, signs)
    # Credit balance (-400 canonical) reads as +400 naturally.
    assert list(out) == [400.0, -200.0]


def test_income_positive_revenue_and_expense():
    # Revenue is credit (-600 canonical) -> +600; expense is debit (+400) -> -400.
    canonical = pd.Series([-600.0, 400.0])
    out = income_positive(canonical)
    assert list(out) == [600.0, -400.0]
    assert out.sum() == 200.0  # net income
