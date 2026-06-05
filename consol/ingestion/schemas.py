"""Declarative expectations for each input file type."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FileSchema:
    """Required and optional columns for an input file (post header-normalize)."""

    name: str
    required: tuple[str, ...]
    optional: tuple[str, ...] = ()
    # Alternative sets of required columns (e.g. TB by debit/credit OR signed amount).
    alternatives: tuple[tuple[str, ...], ...] = field(default_factory=tuple)


TB_SCHEMA = FileSchema(
    name="trial balance",
    required=("account_code",),
    optional=("account_desc", "debit", "credit", "amount"),
    # Either debit/credit columns OR a signed amount column must be present.
    alternatives=(("debit", "credit"), ("amount",)),
)

MAPPING_SCHEMA = FileSchema(
    name="account mapping",
    required=("account_code", "statement", "caption", "normal_sign"),
    optional=(
        "account_desc",
        "caption_order",
        "cf_category",
        "wc_class",
        "is_equity",
        "is_cash",
    ),
)
