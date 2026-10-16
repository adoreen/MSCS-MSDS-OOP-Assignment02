"""Corporate income tax and withholding tax on dividends."""

from __future__ import annotations

from decimal import Decimal

from .base import Tax
from .context import ResultLine, TaxContext, TaxResult
from .exceptions import InvalidIncomeError
from .money import Money
from .rates import CIT_RATE, DIVIDEND_WHT_RATE
from .schedules import format_rate


class CorporateIncomeTax(Tax):
    """Corporate income tax: ``rate x (revenue - allowable deductions)``.

    A negative chargeable income is an assessed loss: the tax is zero and the
    loss is reported in ``notes["assessed_loss"]`` (to carry forward).
    """

    name = "CIT"

    def __init__(self, rate: Decimal = CIT_RATE) -> None:
        self.rate = rate

    def chargeable_income(self, ctx: TaxContext) -> Money:
        """Revenue minus allowable deductions (may be negative)."""
        if ctx.revenue is None:
            raise InvalidIncomeError("revenue is required for corporate income tax")
        return ctx.revenue - Money.sum(d.amount for d in ctx.deductions)

    def calculate(self, ctx: TaxContext) -> TaxResult:
        """Apply the rate to chargeable income."""
        chargeable = self.chargeable_income(ctx)
        taxable = chargeable.max_zero()
        lines = [
            ResultLine("Revenue", ctx.revenue, "", Money.zero()),  # type: ignore[arg-type]
            *(ResultLine(f"Less: {d.description}", d.amount, "", Money.zero()) for d in ctx.deductions),
            ResultLine("Chargeable income", taxable, format_rate(self.rate), taxable * self.rate),
        ]
        notes = {"chargeable_income": chargeable, "assessed_loss": (-chargeable).max_zero()}
        return self._result(taxable, lines, schedule=f"CIT {format_rate(self.rate)}", notes=notes)


class DividendWithholdingTax(Tax):
    """Final withholding tax on dividends paid to a shareholder (used by the planner)."""

    name = "WHT (dividends)"

    def __init__(self, rate: Decimal = DIVIDEND_WHT_RATE) -> None:
        self.rate = rate

    def calculate(self, ctx: TaxContext) -> TaxResult:
        """Withhold ``rate`` of the dividend."""
        if ctx.dividends is None:
            raise InvalidIncomeError("dividends is required for dividend withholding tax")
        line = ResultLine("Dividend paid", ctx.dividends, format_rate(self.rate), ctx.dividends * self.rate)
        return self._result(ctx.dividends, [line], schedule=f"WHT {format_rate(self.rate)}")
