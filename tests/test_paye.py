"""PAYE boundary tests (FY 2026/27 resident schedule = assignment baseline) and schedule selection."""

import datetime as dt
from decimal import Decimal

import pytest

from uganda_tax import PAYE, InvalidIncomeError, Money, NoScheduleForDateError, Residency, TaxContext

FY2026 = dt.date(2026, 8, 31)
FY2025 = dt.date(2026, 3, 31)


def paye(income: int | str, on: dt.date = FY2026, residency: Residency = Residency.RESIDENT):
    return PAYE().calculate(TaxContext(on=on, gross_pay=Money(income), residency=residency))


# Expected values worked by hand from the brief's schedule:
#   410,000    -> 20% x 75,000                         = 15,000
#   485,000    -> 15,000 + 25% x 75,000                = 33,750
#   10,000,000 -> 33,750 + 30% x 9,515,000             = 2,888,250
#   10,000,001 -> 2,888,250 + 30% x 1 + 10% x 1        = 2,888,250.40
@pytest.mark.parametrize(
    ("income", "exact", "rounded"),
    [
        (0, "0", 0),
        (335_000, "0", 0),
        (335_001, "0.20", 0),
        (335_005, "1.00", 1),
        (410_000, "15000", 15_000),
        (410_001, "15000.25", 15_000),
        (485_000, "33750", 33_750),
        (485_001, "33750.30", 33_750),
        (10_000_000, "2888250", 2_888_250),
        (10_000_001, "2888250.40", 2_888_250),
        (10_000_005, "2888252.00", 2_888_252),
    ],
)
def test_resident_band_edges(income: int, exact: str, rounded: int) -> None:
    result = paye(income)
    assert result.unrounded == Money(exact)
    assert result.amount == Money(rounded)


def test_surcharge_line_appears_only_above_threshold() -> None:
    assert not any("Surcharge" in line.description for line in paye(10_000_000).lines)
    assert any("Surcharge" in line.description for line in paye(10_000_001).lines)


def test_marginal_rate_is_40_percent_above_10m() -> None:
    assert paye(20_000_001).unrounded - paye(20_000_000).unrounded == Money("0.40")


@pytest.mark.parametrize(
    ("income", "expected"),
    [(335_000, 33_500), (410_000, 48_500), (500_000, 75_500), (10_000_001, 2_925_500)],
)
def test_non_resident_schedule(income: int, expected: int) -> None:
    # 10,000,001: 48,500 + 30% x 9,590,001 + 10% x 1 = 2,925,500.40
    assert paye(income, residency=Residency.NON_RESIDENT).amount == Money(expected)


def test_previous_year_schedule_selected_by_date() -> None:
    # FY 2025/26: 25,000 + 30% x (500,000 - 410,000) = 52,000
    assert paye(500_000, on=FY2025).amount == Money(52_000)
    assert paye(500_000, on=FY2026).amount == Money(38_250)


def test_no_schedule_for_old_date() -> None:
    with pytest.raises(NoScheduleForDateError):
        paye(500_000, on=dt.date(2020, 1, 1))


def test_allowances_and_pre_paye_deductions() -> None:
    ctx = TaxContext(
        on=FY2026, gross_pay=Money(400_000), allowances=Money(100_000), pre_paye_deductions=Money(15_000)
    )
    result = PAYE().calculate(ctx)
    assert result.base == Money(485_000)
    assert result.amount == Money(33_750)


def test_invalid_inputs_raise() -> None:
    with pytest.raises(InvalidIncomeError):
        TaxContext(on=FY2026, gross_pay=Money(-1))
    with pytest.raises(InvalidIncomeError):
        PAYE().calculate(TaxContext(on=FY2026))  # no gross pay
    with pytest.raises(InvalidIncomeError):
        PAYE().calculate(
            TaxContext(on=FY2026, gross_pay=Money(10), pre_paye_deductions=Money(20))
        )


def test_effective_rate() -> None:
    assert paye(485_000).effective_rate == Decimal(33_750) / Decimal(485_000)
