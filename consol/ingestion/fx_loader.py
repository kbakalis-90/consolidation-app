"""Load an FX-rates file (closing + average rate per currency)."""

from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

import pandas as pd

from consol.ingestion.readers import IngestionError, read_table
from consol.ingestion.schemas import FileSchema
from consol.ingestion.validators import require_columns, to_numeric

FX_SCHEMA = FileSchema(
    name="FX rates",
    required=("currency", "closing_rate", "average_rate"),
)


def load_fx(source: str | Path | BinaryIO | bytes, filename: str | None = None) -> pd.DataFrame:
    """Return a DataFrame with columns ``currency, closing_rate, average_rate``."""
    df = read_table(source, filename)
    require_columns(df, FX_SCHEMA)

    out = pd.DataFrame()
    out["currency"] = df["currency"].astype(str).str.strip().str.upper()
    out["closing_rate"] = to_numeric(df["closing_rate"], "closing_rate", "FX rates")
    out["average_rate"] = to_numeric(df["average_rate"], "average_rate", "FX rates")

    out = out[out["currency"] != ""].reset_index(drop=True)
    if out.empty:
        raise IngestionError("FX file has no usable rows.")
    if (out[["closing_rate", "average_rate"]] <= 0).any().any():
        raise IngestionError("FX rates must be positive and non-zero.")
    return out
