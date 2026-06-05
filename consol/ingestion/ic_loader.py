"""Load an intercompany-balances file (entity codes, not yet resolved to ids)."""

from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

import pandas as pd

from consol.ingestion.readers import IngestionError, read_table
from consol.ingestion.schemas import FileSchema
from consol.ingestion.validators import require_columns, to_numeric
from consol.models.enums import ICType

IC_SCHEMA = FileSchema(
    name="intercompany balances",
    required=("entity_code", "counterparty_code", "ic_type", "amount_local"),
    optional=("caption",),
)

_VALID_IC = {t.value for t in ICType}


def load_ic(source: str | Path | BinaryIO | bytes, filename: str | None = None) -> pd.DataFrame:
    """Return columns ``entity_code, counterparty_code, ic_type, caption, amount_local``."""
    df = read_table(source, filename)
    require_columns(df, IC_SCHEMA)

    out = pd.DataFrame()
    out["entity_code"] = df["entity_code"].astype(str).str.strip()
    out["counterparty_code"] = df["counterparty_code"].astype(str).str.strip()
    out["ic_type"] = df["ic_type"].astype(str).str.strip().str.lower()
    out["caption"] = df["caption"].astype(str).str.strip() if "caption" in df.columns else ""
    out["amount_local"] = to_numeric(df["amount_local"], "amount_local", "IC balances")

    bad = out.loc[~out["ic_type"].isin(_VALID_IC), "ic_type"].unique()
    if len(bad):
        raise IngestionError(
            f"IC 'ic_type' must be one of {sorted(_VALID_IC)}; got: {', '.join(map(str, bad[:5]))}."
        )
    self_ref = out[out["entity_code"] == out["counterparty_code"]]
    if not self_ref.empty:
        raise IngestionError("IC balances cannot have entity_code == counterparty_code.")

    out = out[(out["entity_code"] != "") & (out["counterparty_code"] != "")].reset_index(drop=True)
    if out.empty:
        raise IngestionError("IC file has no usable rows.")
    return out
