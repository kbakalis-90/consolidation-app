import pandas as pd

from consol.checks import (
    cashflow_checks,
    consolidation_checks,
    ingestion_checks,
    statement_checks,
)
from consol.domain.statements import (
    SECTION_ASSETS,
    SECTION_LIABILITIES,
    build_statements,
)
from consol.models.enums import StatementType
from consol.models.results import ConsolidationResult, StatementResult


def _consol_result(elim: pd.DataFrame, matched_bs: float, matched_pl: float) -> ConsolidationResult:
    return ConsolidationResult(
        balance_sheet=StatementResult(StatementType.BS, "EUR", pd.DataFrame()),
        profit_and_loss=StatementResult(StatementType.PL, "EUR", pd.DataFrame()),
        eliminations=elim,
        ic_reconciliation=pd.DataFrame(),
        cta_rollforward=pd.DataFrame(),
        meta={"matched_bs": matched_bs, "matched_pl": matched_pl},
    )


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


def test_eliminations_net_to_zero_passes_when_matched():
    # Each side removes exactly the matched 50; nets to zero AND ties to matched_bs.
    elim = pd.DataFrame(
        [
            {
                "statement": StatementType.BS.value,
                "section": SECTION_ASSETS,
                "caption": "Trade receivables",
                "amount": -50.0,
            },
            {
                "statement": StatementType.BS.value,
                "section": SECTION_LIABILITIES,
                "caption": "Trade payables",
                "amount": -50.0,
            },
        ]
    )
    res = consolidation_checks.eliminations_net_to_zero(_consol_result(elim, 50.0, 0.0), 0.01)
    assert res.passed


def test_eliminations_net_to_zero_fails_when_under_eliminated():
    # Deltas still net to zero (the old tautology would pass) but each side only
    # removed half of the matched 50 that drove the elimination -> must FAIL now.
    elim = pd.DataFrame(
        [
            {
                "statement": StatementType.BS.value,
                "section": SECTION_ASSETS,
                "caption": "Trade receivables",
                "amount": -25.0,
            },
            {
                "statement": StatementType.BS.value,
                "section": SECTION_LIABILITIES,
                "caption": "Trade payables",
                "amount": -25.0,
            },
        ]
    )
    # Sanity: the legacy comparison (asset_side - liab_side) is zero, i.e. tautology.
    assert abs(-25.0 - (-25.0)) < 0.01
    res = consolidation_checks.eliminations_net_to_zero(_consol_result(elim, 50.0, 0.0), 0.01)
    assert not res.passed
    assert res.is_blocking


def _cf(translated_net, section_sum, fx_effect, expected_fx):
    from consol.models.results import CashFlowResult

    return CashFlowResult(
        method="indirect",
        currency="EUR",
        lines=pd.DataFrame(columns=["section", "line", "amount"]),
        net_change=translated_net + fx_effect,
        opening_cash=100.0,
        closing_cash=100.0 + translated_net + fx_effect,
        meta={
            "translated_net": translated_net,
            "section_sum": section_sum,
            "fx_effect": fx_effect,
            "expected_fx_effect": expected_fx,
        },
    )


def test_consolidated_indirect_ties_passes_when_consistent():
    cf = _cf(translated_net=36.0, section_sum=36.0, fx_effect=4.0, expected_fx=4.0)
    assert cashflow_checks.consolidated_indirect_ties_to_cash(cf, 0.01).passed


def test_consolidated_indirect_ties_fails_when_fx_plug_absorbs_gap():
    # net_change == movement by construction (old indirect_ties_to_cash would pass)
    # but the FX plug (10) does not match the rate-spread expectation (4).
    cf = _cf(translated_net=30.0, section_sum=30.0, fx_effect=10.0, expected_fx=4.0)
    movement = cf.closing_cash - cf.opening_cash
    assert abs(cf.net_change - movement) < 0.01  # legacy check is a tautology here
    res = cashflow_checks.consolidated_indirect_ties_to_cash(cf, 0.01)
    assert not res.passed
    assert res.is_blocking


def test_consolidated_indirect_ties_fails_on_dropped_section():
    cf = _cf(translated_net=36.0, section_sum=30.0, fx_effect=4.0, expected_fx=4.0)
    assert not cashflow_checks.consolidated_indirect_ties_to_cash(cf, 0.01).passed
