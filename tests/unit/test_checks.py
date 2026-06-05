import pandas as pd

from consol.checks import ingestion_checks, statement_checks
from consol.domain.statements import build_statements


def test_tb_balances_pass(sample_tb):
    assert ingestion_checks.tb_balances(sample_tb, 0.01).passed


def test_tb_balances_fail():
    tb = pd.DataFrame({"account_code": ["1"], "account_desc": ["x"], "amount_local": [50.0]})
    res = ingestion_checks.tb_balances(tb, 0.01)
    assert not res.passed
    assert res.is_blocking


def test_all_accounts_mapped_detects_gap(sample_tb, sample_mapping):
    mapping = sample_mapping[sample_mapping["account_code"] != "5000"]
    res = ingestion_checks.all_accounts_mapped(sample_tb, mapping)
    assert not res.passed
    assert "5000" in res.detail


def test_no_duplicate_accounts(sample_tb):
    dup = pd.concat([sample_tb, sample_tb.iloc[[0]]], ignore_index=True)
    assert ingestion_checks.no_duplicate_accounts(sample_tb, "trial balance").passed
    assert not ingestion_checks.no_duplicate_accounts(dup, "trial balance").passed


def test_sign_sanity_flags_wrong_direction(sample_tb, sample_mapping):
    bad = sample_tb.copy()
    bad.loc[bad["account_code"] == "1000", "amount_local"] = -10.0  # asset with credit balance
    res = ingestion_checks.sign_sanity(bad, sample_mapping)
    assert not res.passed


def test_bs_balances_check(sample_tb, sample_mapping):
    bundle = build_statements(sample_tb, sample_mapping, "EUR")
    assert statement_checks.bs_balances(bundle, 0.01).passed


def test_fx_completeness_pass():
    rates = pd.DataFrame(
        {"currency": ["USD", "EUR"], "closing_rate": [1.25, 1.0], "average_rate": [1.1, 1.0]}
    )
    res = ingestion_checks.fx_completeness({"USD", "EUR"}, rates, "EUR")
    assert res.passed


def test_fx_completeness_missing_currency():
    rates = pd.DataFrame({"currency": ["EUR"], "closing_rate": [1.0], "average_rate": [1.0]})
    res = ingestion_checks.fx_completeness({"USD", "EUR"}, rates, "EUR")
    assert not res.passed
    assert "USD" in res.detail


def test_fx_completeness_group_rate_not_one():
    rates = pd.DataFrame(
        {"currency": ["USD", "EUR"], "closing_rate": [1.25, 1.2], "average_rate": [1.1, 1.2]}
    )
    res = ingestion_checks.fx_completeness({"USD", "EUR"}, rates, "EUR")
    assert not res.passed
