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


def find_duplicates(df: pd.DataFrame, keys: str | list[str]) -> pd.DataFrame:
    """Return the rows whose ``keys`` combination appears more than once.

    ``keys`` may be a single column name or a list of columns (a composite key).
    The returned frame keeps every offending row, ordered by the key columns, so
    callers can surface exactly which lines collide.
    """
    cols = [keys] if isinstance(keys, str) else list(keys)
    dup_mask = df.duplicated(subset=cols, keep=False)
    if not dup_mask.any():
        return df.iloc[0:0][cols]
    return df.loc[dup_mask, cols].sort_values(cols).reset_index(drop=True)


def normalize_caption(series: pd.Series) -> pd.Series:
    """Collapse blank/NaN/whitespace-only captions to a single canonical ``""``.

    ``astype(str)`` would turn a NaN cell into the literal string ``"nan"`` while
    a whitespace-only cell strips to ``""`` — two different keys for what is the
    same blank caption. Normalizing here lets identical lines collide on the
    composite IC key (and the DB UNIQUE index).
    """
    cleaned = series.where(series.notna(), "").astype(str).str.strip()
    return cleaned.replace({"nan": "", "none": "", "None": ""})
