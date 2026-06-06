"""Load a cash-transaction file for the direct method."""

from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

import pandas as pd

from consol.ingestion.readers import IngestionError, read_table
from consol.ingestion.schemas import FileSchema
from consol.ingestion.validators import find_duplicates, require_columns, to_numeric
from consol.models.enums import CFCategory, FlowSign

CASH_SCHEMA = FileSchema(
    name="cash transactions",
    required=("cf_category", "direct_line", "flow_sign", "amount_local"),
)

_VALID_CF = {c.value for c in CFCategory}
_VALID_FLOW = {f.value for f in FlowSign}


def load_cash(source: str | Path | BinaryIO | bytes, filename: str | None = None) -> pd.DataFrame:
    """Return columns ``cf_category, direct_line, flow_sign, amount_local``."""
    df = read_table(source, filename)
    require_columns(df, CASH_SCHEMA)

    out = pd.DataFrame()
    out["cf_category"] = df["cf_category"].astype(str).str.strip().str.lower()
    out["direct_line"] = df["direct_line"].astype(str).str.strip()
    out["flow_sign"] = df["flow_sign"].astype(str).str.strip().str.lower()
    out["amount_local"] = to_numeric(df["amount_local"], "amount_local", "cash transactions")

    bad_cf = out.loc[~out["cf_category"].isin(_VALID_CF), "cf_category"].unique()
    if len(bad_cf):
        raise IngestionError(
            f"Cash 'cf_category' must be one of {sorted(_VALID_CF)}; "
            f"got: {', '.join(map(str, bad_cf[:5]))}."
        )
    bad_flow = out.loc[~out["flow_sign"].isin(_VALID_FLOW), "flow_sign"].unique()
    if len(bad_flow):
        raise IngestionError(
            f"Cash 'flow_sign' must be one of {sorted(_VALID_FLOW)}; "
            f"got: {', '.join(map(str, bad_flow[:5]))}."
        )

    out = out[out["direct_line"] != ""].reset_index(drop=True)
    if out.empty:
        raise IngestionError("Cash file has no usable rows.")

    # A within-file duplicate on (cf_category, direct_line) would hit the DB
    # UNIQUE constraint; surface it as a friendly error instead.
    dups = find_duplicates(out, ["cf_category", "direct_line"])
    if not dups.empty:
        pairs = dups.drop_duplicates().head(5)
        listing = ", ".join(f"{r.cf_category}/{r.direct_line}" for r in pairs.itertuples())
        raise IngestionError(
            f"Cash file has duplicate (cf_category, direct_line) line(s): {listing}."
        )
    return out
