"""Sign-convention helpers.

Canonical internal representation: **debit positive, credit negative**. TB
amounts are stored this way. Presentation re-signs amounts so each statement
reads naturally:

* Balance sheet -> "natural" amounts: a positive number means the account holds
  its expected balance direction (asset debit / liability & equity credit).
* P&L -> "income-positive" amounts: revenue positive, expenses negative, so the
  lines sum to net income.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from consol.models.enums import NormalSign

CAPTION_CURRENT_YEAR_RESULT = "Result for the period"
CAPTION_UNMAPPED = "UNMAPPED"


def natural_amount(canonical: pd.Series, normal_sign: pd.Series) -> pd.Series:
    """Re-sign canonical amounts to natural (positive when in normal direction)."""
    factor = np.where(normal_sign.str.lower() == NormalSign.DEBIT.value, 1.0, -1.0)
    return canonical.astype(float) * factor


def income_positive(canonical: pd.Series) -> pd.Series:
    """P&L presentation: revenue (credit) positive, expenses (debit) negative."""
    return -canonical.astype(float)
