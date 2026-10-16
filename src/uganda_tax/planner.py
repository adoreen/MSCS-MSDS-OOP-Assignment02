"""Extension B: a TaxPlanner that compares ways of extracting company profit.

Question answered: an owner-managed company has a pre-tax profit ``P`` for a
year, before paying its owner. Is it better to pay ``P`` out as **salary** or
to pay corporate tax and distribute the rest as a **dividend**?

* **Salary:** the whole budget ``P`` is spent on employment. Salary and
  employer NSSF are deductible, so CIT is zero. The monthly salary ``S``
  satisfies ``12 * S * (1 + employer NSSF rate) = P``. The owner pays PAYE, LST
  and 5% NSSF. NSSF is retirement savings, not a tax, so it is reported apart
  from tax: both NSSF shares are money the owner eventually gets back.
* **Dividend:** CIT at 30% on ``P``, then 15% withholding tax on the dividend.

Simplifications (stated in the notebook): a single owner-employee, no other
income, no capital allowances, and salary assumed to be reasonable remuneration.
"""

from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal

from .cit import CorporateIncomeTax, DividendWithholdingTax
from .context import TaxContext
from .exceptions import InvalidIncomeError
from .money import Money
from .nssf import NSSF
from .payroll import PayrollPipeline, Payslip


@dataclass(frozen=True)
class ScenarioOutcome:
    """Result of one profit-extraction scenario for one year."""

    scenario: str
    profit: Money
    taxes: dict[str, Money]
    savings: dict[str, Money] = field(default_factory=dict)

    @property
    def total_tax(self) -> Money:
        """All taxes paid by the company and the owner."""
        return Money.sum(self.taxes.values())

    @property
    def total_savings(self) -> Money:
        """NSSF contributions (employee plus employer) credited to the owner."""
        return Money.sum(self.savings.values())

    @property
    def cash_to_owner(self) -> Money:
        """Money the owner receives now (excluding NSSF savings)."""
        return self.profit - self.total_tax - self.total_savings

    @property
    def effective_tax_rate(self) -> Decimal:
        """Total tax as a share of profit."""
        return self.total_tax.amount / self.profit.amount if self.profit else Decimal(0)


class Scenario(ABC):
    """A way of turning a year's profit into money for the owner."""

    name: str = "Scenario"

    @abstractmethod
    def evaluate(self, profit: Money, fy_start: dt.date) -> ScenarioOutcome:
        """Compute taxes and savings for the year starting ``fy_start``."""

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"


def _months(fy_start: dt.date) -> list[dt.date]:
    """The first day of each of the 12 months of a financial year."""
    return [
        dt.date(fy_start.year + (fy_start.month - 1 + i) // 12, (fy_start.month - 1 + i) % 12 + 1, 1)
        for i in range(12)
    ]


class SalaryScenario(Scenario):
    """Pay the whole profit out as monthly salary (plus employer NSSF)."""

    name = "Salary"

    def __init__(self, payroll: PayrollPipeline | None = None) -> None:
        self.payroll = payroll or PayrollPipeline()

    def monthly_salary(self, profit: Money) -> Money:
        """Salary such that 12 x (salary + employer NSSF) equals the profit."""
        employer_rate = self.payroll.nssf.employer_rate
        return (profit / 12 / (1 + employer_rate)).rounded()

    def payslips(self, profit: Money, fy_start: dt.date) -> list[Payslip]:
        """The 12 payslips for the year."""
        salary = self.monthly_salary(profit)
        return self.payroll.run_many(TaxContext(on=month, gross_pay=salary) for month in _months(fy_start))

    def evaluate(self, profit: Money, fy_start: dt.date) -> ScenarioOutcome:
        slips = self.payslips(profit, fy_start)
        # Any rounding difference stays in the company, so it is taxed as profit.
        paid_out = Money.sum(s.employer_cost for s in slips)
        retained = (profit - paid_out).max_zero()
        cit = CorporateIncomeTax().calculate(TaxContext(on=fy_start, revenue=retained)).amount
        return ScenarioOutcome(
            scenario=self.name,
            profit=profit,
            taxes={
                "PAYE": Money.sum(s.paye.amount for s in slips),
                "LST": Money.sum(s.lst.amount for s in slips),
                "CIT": cit,
            },
            savings={
                "NSSF employee": Money.sum(s.nssf.amount for s in slips),
                "NSSF employer": Money.sum(s.nssf_employer for s in slips),
            },
        )


class DividendScenario(Scenario):
    """Pay CIT on the profit, then distribute the rest as a dividend."""

    name = "Dividend"

    def __init__(
        self,
        cit: CorporateIncomeTax | None = None,
        wht: DividendWithholdingTax | None = None,
    ) -> None:
        self.cit = cit or CorporateIncomeTax()
        self.wht = wht or DividendWithholdingTax()

    def evaluate(self, profit: Money, fy_start: dt.date) -> ScenarioOutcome:
        cit = self.cit.calculate(TaxContext(on=fy_start, revenue=profit)).amount
        dividend = profit - cit
        wht = self.wht.calculate(TaxContext(on=fy_start, dividends=dividend)).amount
        return ScenarioOutcome(scenario=self.name, profit=profit, taxes={"CIT": cit, "WHT": wht})


@dataclass(frozen=True)
class Comparison:
    """Two outcomes side by side."""

    first: ScenarioOutcome
    second: ScenarioOutcome

    @property
    def cash_difference(self) -> Money:
        """Cash to owner under ``second`` minus under ``first``."""
        return self.second.cash_to_owner - self.first.cash_to_owner

    @property
    def tax_difference(self) -> Money:
        """Total tax under ``second`` minus under ``first``."""
        return self.second.total_tax - self.first.total_tax

    @property
    def better_for_cash(self) -> str:
        """Scenario that leaves the owner more cash now."""
        return self.second.scenario if self.cash_difference > Money.zero() else self.first.scenario

    @property
    def lower_tax(self) -> str:
        """Scenario with the lower total tax."""
        return self.second.scenario if self.tax_difference < Money.zero() else self.first.scenario

    def summary(self) -> str:
        """One-paragraph plain-English comparison."""
        a, b = self.first, self.second
        return (
            f"On a profit of {a.profit}: {a.scenario} costs {a.total_tax} in tax "
            f"({a.effective_tax_rate:.1%}) and leaves {a.cash_to_owner} in cash plus "
            f"{a.total_savings} in NSSF savings; {b.scenario} costs {b.total_tax} "
            f"({b.effective_tax_rate:.1%}) and leaves {b.cash_to_owner} in cash plus "
            f"{b.total_savings} in savings. Lowest tax: {self.lower_tax}."
        )


class TaxPlanner:
    """Compares two :class:`Scenario` objects for a given profit and year."""

    def __init__(self, first: Scenario | None = None, second: Scenario | None = None) -> None:
        self.first = first or SalaryScenario()
        self.second = second or DividendScenario()

    def compare(self, profit: Money, fy_start: dt.date) -> Comparison:
        """Evaluate both scenarios on the same profit and year."""
        if profit.is_negative() or not profit:
            raise InvalidIncomeError("Profit must be positive to plan an extraction")
        return Comparison(self.first.evaluate(profit, fy_start), self.second.evaluate(profit, fy_start))

    def sweep(self, profits: list[Money], fy_start: dt.date) -> list[Comparison]:
        """Compare the scenarios across a range of profits."""
        return [self.compare(p, fy_start) for p in profits]
