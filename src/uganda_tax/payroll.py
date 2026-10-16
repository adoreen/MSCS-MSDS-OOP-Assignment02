"""Payroll pipeline: from gross pay to net pay.

Order of deductions
-------------------
1. **NSSF** is computed on employment income (gross pay plus allowances). The
   employee's 5% is *not* deductible for PAYE in Uganda, so it does not
   change the PAYE base. Computing it first only means it appears first on the payslip.
2. **Local Service Tax** is computed from employment income. As the brief
   specifies, it is a deduction allowed *before* PAYE, so it must be known
   before PAYE can be computed.
3. **PAYE** is charged on employment income minus LST.
4. **Net pay** = employment income - employee NSSF - LST - PAYE.

Only LST changes another tax's base, so it is the only ordering that matters
for the amounts: LST must come before PAYE.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from dataclasses import dataclass

from .context import TaxContext, TaxResult
from .exceptions import InvalidIncomeError
from .lst import LocalServiceTax
from .money import Money
from .nssf import NSSF
from .paye import PAYE


@dataclass(frozen=True)
class Payslip:
    """The outcome of running one employee-month through the pipeline."""

    on: dt.date
    gross_pay: Money
    allowances: Money
    nssf: TaxResult
    lst: TaxResult
    paye: TaxResult

    @property
    def employment_income(self) -> Money:
        """Gross pay plus allowances."""
        return self.gross_pay + self.allowances

    @property
    def nssf_employer(self) -> Money:
        """Employer NSSF contribution (not deducted from the employee)."""
        return self.nssf.notes["employer"]

    @property
    def total_deductions(self) -> Money:
        """Employee NSSF + LST + PAYE."""
        return self.nssf.amount + self.lst.amount + self.paye.amount

    @property
    def net_pay(self) -> Money:
        """Take-home pay."""
        return self.employment_income - self.total_deductions

    @property
    def employer_cost(self) -> Money:
        """Total cost of the employee to the employer."""
        return self.employment_income + self.nssf_employer

    def as_dict(self) -> dict[str, object]:
        """Flat mapping of the payslip, suitable for a pandas DataFrame row (values in UGX)."""
        return {
            "Date": self.on,
            "Gross pay (UGX)": self.gross_pay.amount,
            "Allowances (UGX)": self.allowances.amount,
            "NSSF employee (UGX)": self.nssf.amount.amount,
            "LST (UGX)": self.lst.amount.amount,
            "PAYE base (UGX)": self.paye.base.amount,
            "PAYE (UGX)": self.paye.amount.amount,
            "Net pay (UGX)": self.net_pay.amount,
            "NSSF employer (UGX)": self.nssf_employer.amount,
            "Schedule": self.paye.schedule,
        }

    def __str__(self) -> str:
        rows = [
            ("Gross pay", self.gross_pay),
            ("Allowances", self.allowances),
            ("Employment income", self.employment_income),
            ("Less NSSF (employee 5%)", -self.nssf.amount),
            ("Less Local Service Tax", -self.lst.amount),
            ("Less PAYE", -self.paye.amount),
            ("Net pay", self.net_pay),
            ("Employer NSSF (10%, not deducted)", self.nssf_employer),
        ]
        width = max(len(label) for label, _ in rows)
        body = "\n".join(f"{label:<{width}}  {money.amount:>14,.0f}" for label, money in rows)
        return f"Payslip for {self.on:%B %Y} ({self.paye.schedule})\n{body}"


class PayrollPipeline:
    """Runs NSSF, LST and PAYE in the documented order (see module docstring).

    The pipeline *composes* tax objects rather than inheriting from them, so
    any of them can be swapped (e.g. a disabled LST, or a test double).
    """

    def __init__(
        self,
        paye: PAYE | None = None,
        nssf: NSSF | None = None,
        lst: LocalServiceTax | None = None,
    ) -> None:
        self.paye = paye or PAYE()
        self.nssf = nssf or NSSF()
        self.lst = lst or LocalServiceTax()

    def run(self, ctx: TaxContext) -> Payslip:
        """Compute one month's payslip."""
        if ctx.gross_pay is None:
            raise InvalidIncomeError("gross_pay is required to run payroll")
        nssf = self.nssf.calculate(ctx)
        lst = self.lst.calculate(ctx)
        paye = self.paye.calculate(ctx.with_changes(pre_paye_deductions=lst.amount))
        return Payslip(ctx.on, ctx.gross_pay, ctx.allowances, nssf, lst, paye)

    def run_many(self, contexts: Iterable[TaxContext]) -> list[Payslip]:
        """Compute a payslip for each context."""
        return [self.run(ctx) for ctx in contexts]

    def __repr__(self) -> str:
        return f"PayrollPipeline({self.nssf!r}, {self.lst!r}, {self.paye!r})"
