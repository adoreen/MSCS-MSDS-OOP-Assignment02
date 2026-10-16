"""Property-based tests (hypothesis): PAYE is non-negative, monotonic and never exceeds income."""

import datetime as dt

from hypothesis import given
from hypothesis import strategies as st

from uganda_tax import PAYE, Money, PayrollPipeline, Residency, TaxContext

DATES = st.sampled_from([dt.date(2025, 9, 1), dt.date(2026, 9, 1), dt.date(2026, 12, 1)])
RESIDENCY = st.sampled_from(list(Residency))
INCOME = st.integers(min_value=0, max_value=200_000_000)
PAYE_ENGINE = PAYE()


def tax(income: int, on: dt.date, residency: Residency) -> Money:
    return PAYE_ENGINE.calculate(TaxContext(on=on, gross_pay=Money(income), residency=residency)).unrounded


@given(INCOME, DATES, RESIDENCY)
def test_tax_is_non_negative(income: int, on: dt.date, residency: Residency) -> None:
    assert tax(income, on, residency) >= Money.zero()


@given(INCOME, INCOME, DATES, RESIDENCY)
def test_tax_is_monotonic_in_income(a: int, b: int, on: dt.date, residency: Residency) -> None:
    low, high = sorted((a, b))
    assert tax(low, on, residency) <= tax(high, on, residency)


@given(INCOME, DATES, RESIDENCY)
def test_tax_never_exceeds_income(income: int, on: dt.date, residency: Residency) -> None:
    assert tax(income, on, residency) <= Money(income)


@given(INCOME, DATES, RESIDENCY)
def test_rounded_tax_also_within_bounds(income: int, on: dt.date, residency: Residency) -> None:
    amount = PAYE_ENGINE.calculate(
        TaxContext(on=on, gross_pay=Money(income), residency=residency)
    ).amount
    assert Money.zero() <= amount <= Money(income)


@given(st.integers(min_value=0, max_value=50_000_000), DATES)
def test_payroll_net_pay_is_between_zero_and_income(income: int, on: dt.date) -> None:
    slip = PayrollPipeline().run(TaxContext(on=on, gross_pay=Money(income)))
    assert Money.zero() <= slip.net_pay <= slip.employment_income
    assert slip.net_pay + slip.total_deductions == slip.employment_income


@given(st.integers(min_value=0, max_value=10**12), st.integers(min_value=0, max_value=10**12))
def test_money_addition_is_commutative_and_exact(a: int, b: int) -> None:
    assert Money(a) + Money(b) == Money(b) + Money(a) == Money(a + b)
