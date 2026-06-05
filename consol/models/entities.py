"""Lightweight dataclasses for reference data."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Entity:
    entity_id: int
    code: str
    name: str
    local_currency: str
    is_active: bool = True
    parent_entity_id: int | None = None


@dataclass(frozen=True)
class Period:
    period_id: int
    year: int
    month: int
    label: str
    is_closed: bool = False

    @staticmethod
    def make_label(year: int, month: int) -> str:
        return f"{year:04d}-{month:02d}"

    def prior_month(self) -> tuple[int, int]:
        """Return (year, month) for the immediately preceding month."""
        if self.month == 1:
            return self.year - 1, 12
        return self.year, self.month - 1

    def prior_year(self) -> tuple[int, int]:
        """Return (year, month) for the same month one year earlier."""
        return self.year - 1, self.month
