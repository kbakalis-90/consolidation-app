"""Load a trial balance into the canonical signed-amount form.

Canonical internal convention: debit positive, credit negative.
"""

from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

import pandas as pd

from consol.ingestion.readers import IngestionError, read_table
from consol.ingestion.schemas import TB_SCHEMA
from consol.ingestion.validators import require_columns, to_numeric


def load_tb(source: str | Path | BinaryIO | bytes, filename: str | None = None) -> pd.DataFrame:
    """Return a DataFrame with columns ``account_code, account_desc, amount_local``.

    Accepts either ``debit``/``credit`` columns or a signed ``amount`` column.
    """
    df = read_table(source, filename)
    require_columns(df, TB_SCHEMA)
    label = "Trial balance"

    out = pd.DataFrame()
    out["account_code"] = df["account_code"].astype(str).str.strip()
    out["account_desc"] = (
        df["account_desc"].astype(str).str.strip() if "account_desc" in df.columns else ""
    )

    if "amount" in df.columns:
        out["amount_local"] = to_numeric(df["amount"], "amount", label)
    else:
        debit = to_numeric(df["debit"], "debit", label)
        credit = to_numeric(df["credit"], "credit", label)
        out["amount_local"] = debit - credit

    # Drop fully blank account codes that some spreadsheets leave as trailing rows.
    out = out[out["account_code"].str.strip() != ""].reset_index(drop=True)
    if out.empty:
        raise IngestionError("Trial balance has no usable rows (all account codes blank).")
    return out
