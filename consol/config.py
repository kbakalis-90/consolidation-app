"""Application configuration.

Defaults can be overridden at runtime via environment variables or by writing
key/value rows into the ``config`` table (see :mod:`consol.persistence`). The
``config`` table is the source of truth at runtime; the values here are the
bootstrap defaults used when a key is absent.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Project root = parent of the ``consol`` package directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "local" / "consol.db"

# FX direction: how a stored rate converts a local-currency amount into the
# group currency. ``local_per_group`` means rate = units of local per 1 group
# unit, so group_amount = local_amount / rate. ``group_per_local`` means
# group_amount = local_amount * rate.
FX_DIRECTION_LOCAL_PER_GROUP = "local_per_group"
FX_DIRECTION_GROUP_PER_LOCAL = "group_per_local"


@dataclass(frozen=True)
class Settings:
    """Bootstrap defaults. Runtime values may be overridden in the config table."""

    group_currency: str = "EUR"
    fx_direction: str = FX_DIRECTION_GROUP_PER_LOCAL
    # Tolerance (in group/local currency units) for "equals zero" / balancing checks.
    balance_tolerance: float = 0.01
    # Larger tolerance for reconciliations affected by FX rounding.
    reconciliation_tolerance: float = 1.0
    db_path: Path = DEFAULT_DB_PATH

    @staticmethod
    def from_env() -> Settings:
        return Settings(
            group_currency=os.environ.get("CONSOL_GROUP_CURRENCY", "EUR"),
            fx_direction=os.environ.get("CONSOL_FX_DIRECTION", FX_DIRECTION_GROUP_PER_LOCAL),
            balance_tolerance=float(os.environ.get("CONSOL_BALANCE_TOLERANCE", "0.01")),
            reconciliation_tolerance=float(os.environ.get("CONSOL_RECON_TOLERANCE", "1.0")),
            db_path=Path(os.environ.get("CONSOL_DB_PATH", str(DEFAULT_DB_PATH))),
        )


SETTINGS = Settings.from_env()
