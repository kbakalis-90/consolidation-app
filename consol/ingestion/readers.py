"""Read Excel/CSV uploads into a DataFrame with normalized headers."""

from __future__ import annotations

import io
from pathlib import Path
from typing import BinaryIO

import pandas as pd


class IngestionError(ValueError):
    """Raised when a file cannot be read or fails structural validation."""


def normalize_headers(df: pd.DataFrame) -> pd.DataFrame:
    """Lower-case, strip, and collapse whitespace in column names."""
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df


def read_table(source: str | Path | BinaryIO | bytes, filename: str | None = None) -> pd.DataFrame:
    """Read a CSV or Excel file based on its extension.

    ``source`` may be a path, a file-like object, or raw bytes (as delivered by
    a Streamlit uploader). ``filename`` is used to detect the extension when the
    source carries no name.
    """
    name = filename
    if name is None and isinstance(source, (str, Path)):
        name = str(source)
    if name is None and hasattr(source, "name"):
        name = source.name  # type: ignore[union-attr]
    if name is None:
        raise IngestionError("Cannot determine file type: no filename provided.")

    ext = Path(name).suffix.lower()
    data: object = io.BytesIO(source) if isinstance(source, bytes) else source

    try:
        if ext in (".xlsx", ".xls"):
            df = pd.read_excel(data, dtype=object)
        elif ext == ".csv":
            df = pd.read_csv(data, dtype=object)
        else:
            raise IngestionError(f"Unsupported file type '{ext}'. Use .csv, .xlsx, or .xls.")
    except IngestionError:
        raise
    except Exception as exc:  # pragma: no cover - passthrough of pandas errors
        raise IngestionError(f"Could not read file '{name}': {exc}") from exc

    if df.empty:
        raise IngestionError(f"File '{name}' contains no rows.")
    return normalize_headers(df)
