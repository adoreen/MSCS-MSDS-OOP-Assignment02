"""Money value object based on :class:`decimal.Decimal`.

Design rules
------------
* Amounts are stored as exact ``Decimal`` values; ``float`` is rejected
  everywhere, because binary floating point cannot represent most decimal
  fractions exactly (see the notebook for a failing example).
* Arithmetic keeps full precision. Rounding happens only when explicitly
  requested via :meth:`Money.rounded`, which the tax classes call once on
  each final liability. The default rule is ``ROUND_HALF_UP`` to whole
  shillings (UGX has no sub-unit in circulation).
* ``Money`` is immutable and hashable; values in different currencies never mix.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from functools import total_ordering
from typing import Iterable, Union

from .exceptions import CurrencyMismatchError, InvalidIncomeError

#: Values accepted where a plain number is expected (never ``float``).
Number = Union[Decimal, int, str]

#: Number of decimal places for UGX after rounding (whole shillings).
UGX_PLACES = 0
DEFAULT_ROUNDING = ROUND_HALF_UP


def to_decimal(value: Number) -> Decimal:
    """Convert ``value`` to ``Decimal``, rejecting ``float`` and non-numeric input.

    Raises:
        TypeError: if ``value`` is a ``float``, ``bool`` or another unsupported type.
        InvalidIncomeError: if a string is not a valid finite number.
    """
    if isinstance(value, bool) or isinstance(value, float):
        raise TypeError(
            f"{type(value).__name__} is not allowed for money; use Decimal, int or str"
        )
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, (int, str)):
        try:
            result = Decimal(value)
        except InvalidOperation as exc:
            raise InvalidIncomeError(f"Not a valid number: {value!r}") from exc
    else:
        raise TypeError(f"Unsupported type for money: {type(value).__name__}")
    if not result.is_finite():
        raise InvalidIncomeError(f"Amount must be finite, got {value!r}")
    return result


@total_ordering
@dataclass(frozen=True, slots=True)
class Money:
    """An immutable amount of money in a single currency (UGX by default).

    Examples:
        >>> Money(1000) + Money("500.5")
        Money('1500.5', 'UGX')
        >>> (Money(335001) * Decimal("0.20")).rounded()
        Money('67000', 'UGX')
    """

    amount: Decimal
    currency: str = "UGX"

    def __init__(self, amount: Number = 0, currency: str = "UGX") -> None:
        object.__setattr__(self, "amount", to_decimal(amount))
        object.__setattr__(self, "currency", currency.upper())

    # ----- construction helpers -------------------------------------------------
    @classmethod
    def zero(cls, currency: str = "UGX") -> Money:
        """Return a zero amount in ``currency``."""
        return cls(0, currency)

    @classmethod
    def sum(cls, values: Iterable[Money], currency: str = "UGX") -> Money:
        """Add up an iterable of Money values (``builtins.sum`` needs a start value)."""
        total = cls.zero(currency)
        for value in values:
            total = total + value
        return total

    # ----- rounding ---------------------------------------------------------------
    def rounded(self, places: int = UGX_PLACES, rounding: str = DEFAULT_ROUNDING) -> Money:
        """Return a copy rounded to ``places`` decimals using ``rounding`` (half-up by default)."""
        quantum = Decimal(1).scaleb(-places)
        return Money(self.amount.quantize(quantum, rounding=rounding), self.currency)

    # ----- predicates -----------------------------------------------------------
    def is_negative(self) -> bool:
        """True if the amount is below zero."""
        return self.amount < 0

    def max_zero(self) -> Money:
        """Return this amount, or zero if it is negative."""
        return self if self.amount > 0 else Money.zero(self.currency)

    # ----- operators ------------------------------------------------------------
    def _check_same_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise CurrencyMismatchError(
                f"Cannot combine {self.currency} with {other.currency}"
            )

    def __add__(self, other: object) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        self._check_same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: object) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        self._check_same_currency(other)
        return Money(self.amount - other.amount, self.currency)

    def __mul__(self, factor: object) -> Money:
        # Money * Money has no meaning, so only scalar factors are accepted.
        if isinstance(factor, Money) or not isinstance(factor, (Decimal, int, str, float)):
            return NotImplemented
        return Money(self.amount * to_decimal(factor), self.currency)  # type: ignore[arg-type]

    __rmul__ = __mul__

    def __truediv__(self, divisor: object) -> Money:
        if isinstance(divisor, Money) or not isinstance(divisor, (Decimal, int, str, float)):
            return NotImplemented
        value = to_decimal(divisor)  # type: ignore[arg-type]
        if value == 0:
            raise ZeroDivisionError("Cannot divide money by zero")
        return Money(self.amount / value, self.currency)

    def __neg__(self) -> Money:
        return Money(-self.amount, self.currency)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self.currency == other.currency and self.amount == other.amount

    def __hash__(self) -> int:
        return hash((self.amount, self.currency))

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        self._check_same_currency(other)
        return self.amount < other.amount

    def __bool__(self) -> bool:
        return self.amount != 0

    def __repr__(self) -> str:
        return f"Money('{self.amount}', '{self.currency}')"

    def __str__(self) -> str:
        rounded = self.rounded().amount
        return f"{self.currency} {rounded:,.0f}"
