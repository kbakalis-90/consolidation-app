from consol.domain.sign_conventions import CAPTION_CURRENT_YEAR_RESULT
from consol.domain.statements import build_statements


def test_build_statements_balances(sample_tb, sample_mapping):
    bundle = build_statements(sample_tb, sample_mapping, "EUR")
    assert bundle.net_income == 200.0
    assert bundle.total_assets == 800.0
    assert bundle.total_liabilities_equity == 800.0
    assert bundle.balances
    assert bundle.unmapped.empty


def test_pl_lines_sum_to_net_income(sample_tb, sample_mapping):
    bundle = build_statements(sample_tb, sample_mapping, "EUR")
    pl = bundle.profit_and_loss
    assert pl.caption_amount("Revenue") == 600.0
    assert pl.caption_amount("Operating expenses") == -400.0
    assert pl.total == 200.0


def test_current_year_result_in_equity(sample_tb, sample_mapping):
    bundle = build_statements(sample_tb, sample_mapping, "EUR")
    bs = bundle.balance_sheet
    cyr = bs.lines[bs.lines["caption"] == CAPTION_CURRENT_YEAR_RESULT]
    assert not cyr.empty
    assert float(cyr["amount"].iloc[0]) == 200.0
    assert cyr["section"].iloc[0] == "Equity"


def test_unmapped_account_is_surfaced_and_breaks_balance(sample_tb, sample_mapping):
    # Drop the mapping for receivables; that 300 of assets becomes unmapped.
    mapping = sample_mapping[sample_mapping["account_code"] != "1100"]
    bundle = build_statements(sample_tb, mapping, "EUR")
    assert "1100" in set(bundle.unmapped["account_code"])
    # Receivables (an asset) excluded -> assets short by 300, no longer balances.
    assert bundle.total_assets == 500.0
    assert not bundle.balances
