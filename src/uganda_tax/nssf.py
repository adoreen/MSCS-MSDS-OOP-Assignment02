"""National Social Security Fund contributions."""

from __future__ import annotations

from decimal import Decimal

from .base import Tax
from .context import ResultLine, TaxContext, TaxResult
from .money import Money
from .rates import NSSF_EMPLOYEE_RATE, NSSF_EMPLOYER_RATE
from .schedules import format_rate


class NSSF(Tax):
    """NSSF contribution on monthly employment income (gross pay plus allowances).

    The result's ``amount`` is the *employee* share, which is deducted from pay.
    The employer share is reported in ``notes["employer"]``; it is a cost to
    the employer and does not reduce net pay.
    """

    name = "NSSF"

    def __init__(
        self,
        employee_rate: Decimal = NSSF_EMPLOYEE_RATE,
        employer_rate: Decimal = NSSF_EMPLOYER_RATE,
    ) -> None:
        self.employee_rate = employee_rate
        self.employer_rate = employer_rate

    def calculate(self, ctx: TaxContext) -> TaxResult:
        """Compute the employee share (and the employer share as a note)."""
        base = ctx.employment_income
        employee = base * self.employee_rate
        employer = (base * self.employer_rate).rounded()
        line = ResultLine("Employee contribution", base, format_rate(self.employee_rate), employee)
        return self._result(
            base, [line], schedule="NSSF Act", notes={"employer": employer, "total": employer + employee.rounded()}
        )

    def __repr__(self) -> str:
        return f"NSSF(employee_rate={self.employee_rate}, employer_rate={self.employer_rate})"


def employer_cost(result: TaxResult) -> Money:
    """Employer NSSF share from an :class:`NSSF` result."""
    return result.notes.get("employer", Money.zero())
