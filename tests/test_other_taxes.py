"""Tests for NSSF, LST, payroll order, VAT, CIT, schedules and the TaxPlanner."""

import datetime as dt
from decimal import Decimal

import pytest

from uganda_tax import (
    NSSF,
    VAT,
    Band,
    CorporateIncomeTax,
    Deduction,
    InvalidIncomeError,
    InvalidSupplyError,
    Invoice,
    InvoiceDirection,
    LocalServiceTax,
    Money,
    PayrollPipeline,
    ProgressiveSchedule,
    ScheduleConfigurationError,
    ScheduleRegistry,
    SupplyType,
    Tax,
    TaxContext,
    TaxPlanner,
)

AUG = dt.date(2026, 8, 1)
DEC = dt.date(2026, 12, 1)


def test_tax_is_abstract() -> None:
    with pytest.raises(TypeError):
        Tax()  # type: ignore[abstract]


# ----- NSSF and LST -------------------------------------------------------------
def test_nssf_shares() -> None:
    result = NSSF().calculate(TaxContext(on=AUG, gross_pay=Money(1_000_000), allowances=Money(200_000)))
    assert result.amount == Money(60_000)
    assert result.notes["employer"] == Money(120_000)


@pytest.mark.parametrize(
    ("income", "annual"),
    [(100_000, 0), (100_001, 5_000), (350_000, 20_000), (1_000_000, 90_000), (1_000_001, 100_000)],
)
def test_lst_annual_bands(income: int, annual: int) -> None:
    assert LocalServiceTax().annual_amount(TaxContext(on=AUG, gross_pay=Money(income))) == Money(annual)


def test_lst_is_spread_over_deduction_months() -> None:
    lst = LocalServiceTax()
    assert lst.calculate(TaxContext(on=AUG, gross_pay=Money(2_000_000))).amount == Money(25_000)
    assert lst.calculate(TaxContext(on=DEC, gross_pay=Money(2_000_000))).amount == Money(0)
    disabled = LocalServiceTax(enabled=False)
    assert disabled.calculate(TaxContext(on=AUG, gross_pay=Money(2_000_000))).amount == Money(0)


def test_payroll_deducts_lst_before_paye() -> None:
    slip = PayrollPipeline().run(TaxContext(on=AUG, gross_pay=Money(2_000_000), allowances=Money(300_000)))
    assert slip.lst.amount == Money(25_000)
    assert slip.paye.base == Money(2_275_000)  # 2,300,000 - LST; NSSF is not deductible
    assert slip.paye.amount == Money(570_750)  # 33,750 + 30% x 1,790,000
    assert slip.net_pay == Money(2_300_000 - 115_000 - 25_000 - 570_750)
    assert slip.employer_cost == Money(2_530_000)


# ----- VAT ------------------------------------------------------------------------
def _invoice(number: str, amount: int, supply: SupplyType, direction=InvoiceDirection.SALE) -> Invoice:
    return Invoice(number, Money(amount), supply, direction)


def test_vat_mixed_supplies() -> None:
    invoices = [
        _invoice("S1", 1_000_000, SupplyType.STANDARD),
        _invoice("S2", 500_000, SupplyType.ZERO_RATED),
        _invoice("S3", 300_000, SupplyType.EXEMPT),
        _invoice("P1", 400_000, SupplyType.STANDARD, InvoiceDirection.PURCHASE),
        _invoice("P2", 100_000, SupplyType.EXEMPT, InvoiceDirection.PURCHASE),
    ]
    result = VAT().calculate(TaxContext(on=AUG, invoices=invoices))
    assert result.notes["output_vat"] == Money(180_000)
    assert result.notes["input_vat"] == Money(72_000)
    assert result.amount == Money(108_000)


def test_vat_refund_position_is_not_negative() -> None:
    invoices = [
        _invoice("S1", 100_000, SupplyType.ZERO_RATED),
        _invoice("P1", 1_000_000, SupplyType.STANDARD, InvoiceDirection.PURCHASE),
    ]
    result = VAT().calculate(TaxContext(on=AUG, invoices=invoices))
    assert result.amount == Money(0)
    assert result.notes["credit_carried_forward"] == Money(180_000)


def test_vat_rounds_per_invoice() -> None:
    result = VAT().calculate(TaxContext(on=AUG, invoices=[_invoice("S1", 1_003, SupplyType.STANDARD)]))
    assert result.amount == Money(181)  # 180.54 -> 181


def test_invalid_invoice() -> None:
    with pytest.raises(InvalidSupplyError):
        _invoice("S1", -5, SupplyType.STANDARD)
    with pytest.raises(InvalidSupplyError):
        Invoice("S2", Money(5), "luxury")  # type: ignore[arg-type]


# ----- CIT ------------------------------------------------------------------------
def test_cit_on_chargeable_income() -> None:
    ctx = TaxContext(
        on=AUG,
        revenue=Money(500_000_000),
        deductions=[Deduction("Salaries", Money(200_000_000)), Deduction("Rent", Money(50_000_000))],
    )
    result = CorporateIncomeTax().calculate(ctx)
    assert result.base == Money(250_000_000)
    assert result.amount == Money(75_000_000)


def test_cit_loss_is_not_taxed() -> None:
    ctx = TaxContext(on=AUG, revenue=Money(10), deductions=[Deduction("Costs", Money(50))])
    result = CorporateIncomeTax().calculate(ctx)
    assert result.amount == Money(0)
    assert result.notes["assessed_loss"] == Money(40)


def test_cit_requires_revenue() -> None:
    with pytest.raises(InvalidIncomeError):
        CorporateIncomeTax().calculate(TaxContext(on=AUG))


# ----- schedules ------------------------------------------------------------------
def test_schedule_validation() -> None:
    with pytest.raises(ScheduleConfigurationError):  # gap between bands
        ProgressiveSchedule(
            name="bad",
            effective_from=AUG,
            effective_to=None,
            bands=(
                Band(Money(0), Money(100), Decimal(0)),
                Band(Money(200), None, Decimal("0.1")),
            ),
        )


def test_registry_rejects_overlap() -> None:
    def schedule(name: str, start: dt.date, end: dt.date | None) -> ProgressiveSchedule:
        return ProgressiveSchedule(name=name, effective_from=start, effective_to=end,
                                   bands=(Band(Money(0), None, Decimal(0)),))

    with pytest.raises(ScheduleConfigurationError):
        ScheduleRegistry("X", [schedule("a", dt.date(2025, 1, 1), None), schedule("b", dt.date(2026, 1, 1), None)])


# ----- planner (extension B) ------------------------------------------------------
def test_planner_dividend_scenario() -> None:
    comparison = TaxPlanner().compare(Money(100_000_000), dt.date(2026, 7, 1))
    dividend = comparison.second
    assert dividend.taxes["CIT"] == Money(30_000_000)
    assert dividend.taxes["WHT"] == Money(10_500_000)  # 15% x 70,000,000
    assert dividend.cash_to_owner == Money(59_500_000)


def test_planner_salary_scenario_spends_whole_budget() -> None:
    comparison = TaxPlanner().compare(Money(120_000_000), dt.date(2026, 7, 1))
    salary = comparison.first
    accounted = salary.total_tax + salary.total_savings + salary.cash_to_owner
    assert accounted == Money(120_000_000)
    assert salary.taxes["LST"] == Money(100_000)
    assert comparison.lower_tax == "Salary"
