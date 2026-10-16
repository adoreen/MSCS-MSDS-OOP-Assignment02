"""Local Service Tax (LST), a local-government levy on employment income."""

from __future__ import annotations

from collections.abc import Collection

from .base import Tax
from .context import ResultLine, TaxContext, TaxResult
from .money import Money
from .rates import LST_SCHEDULE
from .schedules import ScheduleRegistry, StepSchedule

#: Months (July to October) in which employers deduct LST by default.
DEFAULT_DEDUCTION_MONTHS = frozenset({7, 8, 9, 10})


class LocalServiceTax(Tax):
    """Monthly LST instalment.

    The annual LST is looked up from monthly employment income and collected
    in equal instalments during ``deduction_months``. In other months the
    instalment is zero.

    Args:
        registry: Dated LST schedules.
        deduction_months: Calendar months in which an instalment is deducted.
        enabled: Set ``False`` for employees exempt from LST (the brief calls it
            an optional deduction); the result is then always zero.
    """

    name = "LST"

    def __init__(
        self,
        registry: ScheduleRegistry[StepSchedule] | None = None,
        deduction_months: Collection[int] = DEFAULT_DEDUCTION_MONTHS,
        enabled: bool = True,
    ) -> None:
        if not deduction_months or not all(1 <= m <= 12 for m in deduction_months):
            raise ValueError("deduction_months must be a non-empty set of months 1-12")
        self._registry = registry or ScheduleRegistry("LST", [LST_SCHEDULE])
        self.deduction_months = frozenset(deduction_months)
        self.enabled = enabled

    def annual_amount(self, ctx: TaxContext) -> Money:
        """The annual LST due for the context's monthly income."""
        schedule = self._registry.for_date(ctx.on)
        _, amount = schedule.lookup(ctx.employment_income)
        return amount

    def calculate(self, ctx: TaxContext) -> TaxResult:
        """The instalment due in the month of ``ctx.on``."""
        base = ctx.employment_income
        if not self.enabled:
            return self._result(base, [ResultLine("LST not applied", base, "-", Money.zero())])
        schedule = self._registry.for_date(ctx.on)
        annual = self.annual_amount(ctx)
        instalments = len(self.deduction_months)
        if ctx.on.month in self.deduction_months:
            instalment = annual / instalments
            description = f"Instalment ({instalments} per year) of annual {annual}"
        else:
            instalment = Money.zero()
            description = "No instalment due this month"
        line = ResultLine(description, base, f"1/{instalments} of annual", instalment)
        return self._result(base, [line], schedule=schedule.name, notes={"annual": annual})

    def __repr__(self) -> str:
        return f"LocalServiceTax(months={sorted(self.deduction_months)}, enabled={self.enabled})"
