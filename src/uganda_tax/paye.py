"""Pay As You Earn (PAYE) on monthly employment income."""

from __future__ import annotations

from collections.abc import Mapping

from .base import Tax
from .context import Residency, ResultLine, TaxContext, TaxResult
from .exceptions import InvalidIncomeError
from .money import Money
from .rates import default_paye_registries
from .schedules import ProgressiveSchedule, ScheduleRegistry


class PAYE(Tax):
    """Monthly PAYE for resident and non-resident employees.

    The chargeable amount is ``gross_pay + allowances - pre_paye_deductions``
    (the payroll pipeline puts Local Service Tax into ``pre_paye_deductions``).
    The schedule is chosen by residency and by the date in the context.

    Args:
        registries: PAYE schedules keyed by :class:`Residency` value. Defaults to
            the statutory schedules in :mod:`uganda_tax.rates`.
    """

    name = "PAYE"

    def __init__(
        self, registries: Mapping[str, ScheduleRegistry[ProgressiveSchedule]] | None = None
    ) -> None:
        self._registries = dict(registries or default_paye_registries())

    def schedule_for(self, ctx: TaxContext) -> ProgressiveSchedule:
        """Return the schedule in force for the context's residency and date.

        Raises:
            NoScheduleForDateError: if no schedule covers ``ctx.on``.
            InvalidIncomeError: if no schedule exists for the residency status.
        """
        try:
            registry = self._registries[Residency(ctx.residency).value]
        except KeyError as exc:
            raise InvalidIncomeError(f"No PAYE schedule for residency {ctx.residency}") from exc
        return registry.for_date(ctx.on)

    def chargeable_income(self, ctx: TaxContext) -> Money:
        """Employment income minus deductions allowed before PAYE.

        Raises:
            InvalidIncomeError: if gross pay is missing or deductions exceed income.
        """
        income = ctx.employment_income
        chargeable = income - ctx.pre_paye_deductions
        if chargeable.is_negative():
            raise InvalidIncomeError(
                f"Pre-PAYE deductions ({ctx.pre_paye_deductions}) exceed income ({income})"
            )
        return chargeable

    def calculate(self, ctx: TaxContext) -> TaxResult:
        """Apply the progressive bands and the surcharge to the chargeable income."""
        schedule = self.schedule_for(ctx)
        chargeable = self.chargeable_income(ctx)
        lines = schedule.lines(chargeable)
        if not lines:
            lines = [ResultLine("Below threshold", chargeable, "0%", Money.zero())]
        return self._result(chargeable, lines, schedule=schedule.name)

    def __repr__(self) -> str:
        return f"PAYE(residencies={sorted(self._registries)})"
