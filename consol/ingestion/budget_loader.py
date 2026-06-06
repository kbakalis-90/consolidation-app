"""Load an annual budget file (TB-shaped, with a month column)."""

from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

import pandas as pd

from consol.ingestion.readers import IngestionError, read_table
from consol.ingestion.schemas import FileSchema
from consol.ingestion.validators import find_duplicates, require_columns, to_numeric

BUDGET_SCHEMA = FileSchema(
    name="budget",
    required=("account_code", "month", "amount_local"),
    optional=("account_desc",),
)


def load_budget(source: str | Path | BinaryIO | bytes, filename: str | None = None) -> pd.DataFrame:
    """Return columns ``account_code, account_desc, month, amount_local`` (signed)."""
    df = read_table(source, filename)
    require_columns(df, BUDGET_SCHEMA)

    out = pd.DataFrame()
    out["account_code"] = df["account_code"].astype(str).str.strip()
    out["account_desc"] = (
        df["account_desc"].astype(str).str.strip() if "account_desc" in df.columns else ""
    )
    out["month"] = pd.to_numeric(df["month"], errors="coerce")
    out["amount_local"] = to_numeric(df["amount_local"], "amount_local", "budget")

    if out["month"].isna().any() or not out["month"].dropna().between(1, 12).all():
        raise IngestionError("Budget 'month' must be an integer between 1 and 12.")
    out["month"] = out["month"].astype(int)

    out = out[out["account_code"] != ""].reset_index(drop=True)
    if out.empty:
        raise IngestionError("Budget file has no usable rows.")

    # A within-file duplicate on (month, account_code) would hit the DB UNIQUE
    # constraint (entity_id, period_id, account_code); surface it friendlily.
    dups = find_duplicates(out, ["month", "account_code"])
    if not dups.empty:
        pairs = dups.drop_duplicates().head(5)
        listing = ", ".join(f"{int(r.month):02d}/{r.account_code}" for r in pairs.itertuples())
        raise IngestionError(f"Budget file has duplicate (month, account_code) line(s): {listing}.")
    return out
