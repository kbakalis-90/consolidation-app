"""Structural validation shared by all loaders."""

from __future__ import annotations

import pandas as pd

from consol.ingestion.readers import IngestionError
from consol.ingestion.schemas import FileSchema


def require_columns(df: pd.DataFrame, schema: FileSchema) -> None:
    """Raise IngestionError if required (or alternative) columns are missing."""
    cols = set(df.columns)

    missing = [c for c in schema.required if c not in cols]
    if missing:
        raise IngestionError(
            f"{schema.name.title()} file is missing required column(s): {', '.join(missing)}."
        )

    if schema.alternatives:
        if not any(all(c in cols for c in alt) for alt in schema.alternatives):
            options = " OR ".join("(" + ", ".join(alt) + ")" for alt in schema.alternatives)
            raise IngestionError(f"{schema.name.title()} file must contain one of: {options}.")


def to_numeric(series: pd.Series, column: str, file_label: str) -> pd.Series:
    """Coerce a column to float, raising on non-numeric values."""
    coerced = pd.to_numeric(series, errors="coerce")
    bad = series[coerced.isna() & series.notna() & (series.astype(str).str.strip() != "")]
    if not bad.empty:
        raise IngestionError(
            f"{file_label}: column '{column}' has non-numeric value(s): "
            f"{', '.join(map(str, bad.unique()[:5]))}."
        )
    return coerced.fillna(0.0).astype(float)


def find_duplicates(df: pd.DataFrame, key: str) -> list[str]:
    """Return values of ``key`` that appear more than once."""
    counts = df[key].astype(str).str.strip().value_counts()
    return counts[counts > 1].index.tolist()
