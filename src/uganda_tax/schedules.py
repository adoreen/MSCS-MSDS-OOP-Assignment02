"""Rate schedules: progressive bands, step tables, and a date-based registry.

Rates are *data*, not ``if`` chains: a new Finance Act means adding a new
schedule object with its effective dates, not editing calculation code.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Generic, Protocol, TypeVar

from .context import ResultLine
from .exceptions import NoScheduleForDateError, ScheduleConfigurationError
from .money import Money


def format_rate(rate: Decimal) -> str:
    """Format a rate such as ``Decimal("0.25")`` as ``"25%"``."""
    return f"{(rate * 100).normalize():f}%"


@dataclass(frozen=True)
class Band:
    """A marginal-rate band: ``rate`` applies to income in ``(lower, upper]``.

    ``upper=None`` means the band has no ceiling.
    """

    lower: Money
    upper: Money | None
    rate: Decimal

    def __post_init__(self) -> None:
        if self.rate < 0 or self.rate > 1:
            raise ScheduleConfigurationError(f"Band rate must be in [0, 1], got {self.rate}")
        if self.upper is not None and self.upper <= self.lower:
            raise ScheduleConfigurationError(
                f"Band upper ({self.upper}) must exceed lower ({self.lower})"
            )

    def portion(self, income: Money) -> Money:
        """The part of ``income`` that falls inside this band."""
        if income <= self.lower:
            return Money.zero(income.currency)
        top = income if self.upper is None or income < self.upper else self.upper
        return top - self.lower

    def describe(self) -> str:
        """Human-readable label such as ``"335,000 - 410,000"``."""
        upper = "and above" if self.upper is None else f"- {self.upper.amount:,.0f}"
        return f"{self.lower.amount:,.0f} {upper}"


class Dated(Protocol):
    """Anything with an effective date range (used by :class:`ScheduleRegistry`)."""

    name: str
    effective_from: dt.date
    effective_to: dt.date | None

    def is_in_force(self, on: dt.date) -> bool: ...


@dataclass(frozen=True)
class _DatedMixin:
    """Shared effective-date behaviour (composition-friendly mixin)."""

    name: str
    effective_from: dt.date
    effective_to: dt.date | None

    def is_in_force(self, on: dt.date) -> bool:
        """True if ``on`` lies within ``[effective_from, effective_to]``."""
        return self.effective_from <= on and (self.effective_to is None or on <= self.effective_to)


@dataclass(frozen=True)
class ProgressiveSchedule(_DatedMixin):
    """A marginal-rate schedule with an optional surcharge above a threshold.

    Attributes:
        bands: Contiguous bands starting at zero; the last band is open-ended.
        surcharge_threshold: Income above this attracts ``surcharge_rate`` in
            addition to the band rate (URA's "additional 10% above 10,000,000").
        surcharge_rate: Rate of the surcharge.
        source: Citation for the rates.
    """

    bands: tuple[Band, ...] = ()
    surcharge_threshold: Money | None = None
    surcharge_rate: Decimal = Decimal(0)
    source: str = ""

    def __post_init__(self) -> None:
        if not self.bands:
            raise ScheduleConfigurationError(f"{self.name}: at least one band is required")
        if self.bands[0].lower != Money.zero():
            raise ScheduleConfigurationError(f"{self.name}: first band must start at 0")
        for previous, current in zip(self.bands, self.bands[1:]):
            if previous.upper != current.lower:
                raise ScheduleConfigurationError(
                    f"{self.name}: bands must be contiguous ({previous.describe()} -> "
                    f"{current.describe()})"
                )
        if self.bands[-1].upper is not None:
            raise ScheduleConfigurationError(f"{self.name}: last band must be open-ended")
        if (self.surcharge_threshold is None) != (self.surcharge_rate == 0):
            raise ScheduleConfigurationError(
                f"{self.name}: surcharge threshold and rate must be set together"
            )

    def lines(self, income: Money) -> list[ResultLine]:
        """Breakdown of the tax on ``income``: one line per band touched, plus surcharge."""
        lines: list[ResultLine] = []
        for band in self.bands:
            portion = band.portion(income)
            if not portion:
                continue
            lines.append(
                ResultLine(f"Band {band.describe()}", portion, format_rate(band.rate), portion * band.rate)
            )
        if self.surcharge_threshold is not None and income > self.surcharge_threshold:
            excess = income - self.surcharge_threshold
            lines.append(
                ResultLine(
                    f"Surcharge above {self.surcharge_threshold.amount:,.0f}",
                    excess,
                    format_rate(self.surcharge_rate),
                    excess * self.surcharge_rate,
                )
            )
        return lines

    def tax(self, income: Money) -> Money:
        """Unrounded tax on ``income``."""
        return Money.sum(line.amount for line in self.lines(income))

    def marginal_rate(self, income: Money) -> Decimal:
        """Rate applying to the next shilling above ``income``."""
        rate = next(
            b.rate for b in self.bands if b.upper is None or income < b.upper
        )
        if self.surcharge_threshold is not None and income >= self.surcharge_threshold:
            rate += self.surcharge_rate
        return rate


@dataclass(frozen=True)
class StepRow:
    """A row of a step table: a fixed ``amount`` for income in ``(lower, upper]``."""

    lower: Money
    upper: Money | None
    amount: Money

    def contains(self, income: Money) -> bool:
        """True if ``income`` falls in ``(lower, upper]``."""
        return income > self.lower and (self.upper is None or income <= self.upper)


@dataclass(frozen=True)
class StepSchedule(_DatedMixin):
    """A schedule mapping income bands to a fixed amount (e.g. Local Service Tax).

    Income at or below the first row's lower bound pays nothing.
    """

    rows: tuple[StepRow, ...] = ()
    source: str = ""

    def __post_init__(self) -> None:
        if not self.rows:
            raise ScheduleConfigurationError(f"{self.name}: at least one row is required")
        for previous, current in zip(self.rows, self.rows[1:]):
            if previous.upper != current.lower:
                raise ScheduleConfigurationError(f"{self.name}: rows must be contiguous")
        if self.rows[-1].upper is not None:
            raise ScheduleConfigurationError(f"{self.name}: last row must be open-ended")

    def lookup(self, income: Money) -> tuple[StepRow | None, Money]:
        """Return the matching row (or ``None``) and its amount for ``income``."""
        for row in self.rows:
            if row.contains(income):
                return row, row.amount
        return None, Money.zero(income.currency)


S = TypeVar("S", bound=Dated)


class ScheduleRegistry(Generic[S]):
    """Holds the versions of one schedule and returns the one in force on a date.

    Raises :class:`~uganda_tax.exceptions.ScheduleConfigurationError` if two
    versions overlap, so a lookup can never be ambiguous.
    """

    def __init__(self, tax_name: str, schedules: Iterable[S]) -> None:
        self.tax_name = tax_name
        self._schedules: list[S] = sorted(schedules, key=lambda s: s.effective_from)
        self._check_no_overlap(self._schedules)

    def _check_no_overlap(self, schedules: Sequence[S]) -> None:
        for earlier, later in zip(schedules, schedules[1:]):
            if earlier.effective_to is None or earlier.effective_to >= later.effective_from:
                raise ScheduleConfigurationError(
                    f"{self.tax_name}: schedules {earlier.name!r} and {later.name!r} overlap"
                )

    def for_date(self, on: dt.date) -> S:
        """Return the schedule in force on ``on``.

        Raises:
            NoScheduleForDateError: if no schedule covers ``on``.
        """
        for schedule in self._schedules:
            if schedule.is_in_force(on):
                return schedule
        covered = ", ".join(
            f"{s.effective_from}..{s.effective_to or 'open'}" for s in self._schedules
        )
        raise NoScheduleForDateError(self.tax_name, on, f"modelled periods are {covered}")

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self._schedules)

    def __len__(self) -> int:
        return len(self._schedules)

    def __repr__(self) -> str:
        return f"ScheduleRegistry({self.tax_name!r}, {[s.name for s in self._schedules]})"
