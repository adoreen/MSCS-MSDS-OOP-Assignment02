"""Exception hierarchy for the tax engine.

Every error raised deliberately by the engine derives from :class:`TaxError`,
so callers can catch one type, or handle specific failures individually.
"""

from __future__ import annotations

import datetime as dt


class TaxError(Exception):
    """Base class for all tax-engine errors."""


class InvalidIncomeError(TaxError, ValueError):
    """An income, amount or other monetary input is missing or invalid (e.g. negative)."""


class NoScheduleForDateError(TaxError, LookupError):
    """No rate schedule is in force for the requested date."""

    def __init__(self, tax_name: str, on: dt.date, detail: str = "") -> None:
        self.tax_name = tax_name
        self.on = on
        message = f"No {tax_name} schedule is in force on {on.isoformat()}"
        super().__init__(f"{message}: {detail}" if detail else message)


class CurrencyMismatchError(TaxError, TypeError):
    """Arithmetic or comparison between Money values in different currencies."""


class ScheduleConfigurationError(TaxError, ValueError):
    """A rate schedule is malformed (gaps or overlaps in bands or dates)."""


class InvalidSupplyError(TaxError, ValueError):
    """A VAT invoice is malformed (unknown supply type, negative value, ...)."""
