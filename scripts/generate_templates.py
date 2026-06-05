"""Generate blank input templates into data/templates/.

Run: python -m scripts.generate_templates
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "data" / "templates"

TEMPLATES: dict[str, list[str]] = {
    "trial_balance": ["account_code", "account_desc", "debit", "credit"],
    "account_mapping": [
        "account_code",
        "account_desc",
        "statement",
        "caption",
        "caption_order",
        "cf_category",
        "wc_class",
        "normal_sign",
        "is_equity",
        "is_cash",
    ],
    "ic_balances": ["entity_code", "counterparty_code", "ic_type", "caption", "amount_local"],
    "fx_rates": ["currency", "closing_rate", "average_rate"],
    "cash_transactions": ["cf_category", "direct_line", "flow_sign", "amount_local"],
    "budget": ["account_code", "account_desc", "month", "amount_local"],
}


def generate(directory: Path = TEMPLATES_DIR) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for name, columns in TEMPLATES.items():
        path = directory / f"{name}_template.xlsx"
        pd.DataFrame(columns=columns).to_excel(path, index=False)
        written.append(path)
    return written


if __name__ == "__main__":
    for p in generate():
        print(f"wrote {p}")
