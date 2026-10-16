"""Tests for the Money value object."""

from decimal import ROUND_DOWN, Decimal

import pytest

from uganda_tax import CurrencyMismatchError, InvalidIncomeError, Money


def test_float_is_rejected() -> None:
    with pytest.raises(TypeError):
        Money(0.1)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Money(100) * 0.18  # type: ignore[operator]


def test_invalid_string_is_rejected() -> None:
    with pytest.raises(InvalidIncomeError):
        Money("abc")
    with pytest.raises(InvalidIncomeError):
        Money("NaN")


def test_decimal_arithmetic_is_exact() -> None:
    total = Money.sum([Money("0.1")] * 10)
    assert total == Money(1)
    assert Money("0.1") + Money("0.2") == Money("0.3")


def test_operators() -> None:
    a, b = Money(1_000), Money(250)
    assert a + b == Money(1_250)
    assert a - b == Money(750)
    assert a * Decimal("0.18") == Money(180)
    assert 2 * b == Money(500)
    assert b < a and a > b and a >= Money(1_000)
    assert repr(b) == "Money('250', 'UGX')"
    assert str(Money(1234567)) == "UGX 1,234,567"


def test_rounding_is_half_up_to_shilling_by_default() -> None:
    assert Money("0.5").rounded() == Money(1)
    assert Money("2.5").rounded() == Money(3)  # banker's rounding would give 2
    assert Money("2.49").rounded() == Money(2)
    assert Money("2.99").rounded(rounding=ROUND_DOWN) == Money(2)


def test_currency_mismatch() -> None:
    with pytest.raises(CurrencyMismatchError):
        Money(1, "UGX") + Money(1, "USD")
    with pytest.raises(CurrencyMismatchError):
        _ = Money(1, "UGX") < Money(1, "USD")


def test_money_is_immutable_and_hashable() -> None:
    m = Money(5)
    with pytest.raises(AttributeError):
        m.amount = Decimal(6)  # type: ignore[misc]
    assert len({Money(5), Money("5.0")}) == 1
