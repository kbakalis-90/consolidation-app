"""Load and normalize a per-entity account mapping."""

from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

import pandas as pd

from consol.ingestion.readers import IngestionError, read_table
from consol.ingestion.schemas import MAPPING_SCHEMA
from consol.ingestion.validators import require_columns
from consol.models.enums import CFCategory, NormalSign, StatementType, WCClass

_VALID_STATEMENTS = {s.value for s in StatementType}
_VALID_SIGNS = {s.value for s in NormalSign}
_VALID_CF = {c.value for c in CFCategory}
_VALID_WC = {w.value for w in WCClass}


def _norm_optional(value: object, valid: set[str], column: str) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in ("", "nan", "none"):
        return None
    # Match case-insensitively but return the canonical stored value.
    canonical = {v.lower(): v for v in valid}
    if text.lower() not in canonical:
        raise IngestionError(
            f"Mapping column '{column}' has invalid value '{value}'. "
            f"Allowed: {', '.join(sorted(valid))} (or blank)."
        )
    return canonical[text.lower()]


def _to_bool(value: object) -> int:
    text = str(value).strip().lower()
    return 1 if text in ("1", "true", "yes", "y", "t") else 0


def load_mapping(
    source: str | Path | BinaryIO | bytes, filename: str | None = None
) -> pd.DataFrame:
    """Return a normalized mapping DataFrame ready for ``mapping_repo``."""
    df = read_table(source, filename)
    require_columns(df, MAPPING_SCHEMA)

    out = pd.DataFrame()
    out["account_code"] = df["account_code"].astype(str).str.strip()
    out["account_desc"] = (
        df["account_desc"].astype(str).str.strip() if "account_desc" in df.columns else ""
    )

    statement = df["statement"].astype(str).str.strip().str.upper()
    bad_stmt = statement[~statement.isin(_VALID_STATEMENTS)].unique()
    if len(bad_stmt):
        raise IngestionError(
            f"Mapping 'statement' must be one of {sorted(_VALID_STATEMENTS)}; "
            f"got: {', '.join(map(str, bad_stmt[:5]))}."
        )
    out["statement"] = statement

    out["caption"] = df["caption"].astype(str).str.strip()

    if "caption_order" in df.columns:
        out["caption_order"] = (
            pd.to_numeric(df["caption_order"], errors="coerce").fillna(9999).astype(int)
        )
    else:
        out["caption_order"] = 9999

    sign = df["normal_sign"].astype(str).str.strip().str.lower()
    bad_sign = sign[~sign.isin(_VALID_SIGNS)].unique()
    if len(bad_sign):
        raise IngestionError(
            f"Mapping 'normal_sign' must be one of {sorted(_VALID_SIGNS)}; "
            f"got: {', '.join(map(str, bad_sign[:5]))}."
        )
    out["normal_sign"] = sign

    out["cf_category"] = (
        df["cf_category"].map(lambda v: _norm_optional(v, _VALID_CF, "cf_category"))
        if "cf_category" in df.columns
        else None
    )
    out["wc_class"] = (
        df["wc_class"].map(lambda v: _norm_optional(v, _VALID_WC, "wc_class"))
        if "wc_class" in df.columns
        else None
    )
    out["is_equity"] = df["is_equity"].map(_to_bool) if "is_equity" in df.columns else 0
    out["is_cash"] = df["is_cash"].map(_to_bool) if "is_cash" in df.columns else 0

    out = out[out["account_code"].str.strip() != ""].reset_index(drop=True)
    if out.empty:
        raise IngestionError("Mapping file has no usable rows (all account codes blank).")
    return out
