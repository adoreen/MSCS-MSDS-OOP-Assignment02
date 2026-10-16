"""Value Added Tax on a list of invoices."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from .base import Tax
from .context import Invoice, InvoiceDirection, ResultLine, SupplyType, TaxContext, TaxResult
from .money import Money
from .rates import VAT_STANDARD_RATE
from .schedules import format_rate


class VAT(Tax):
    """Net VAT payable for a period: output VAT on sales minus input VAT on purchases.

    * Standard-rated supplies are taxed at ``standard_rate`` (18%).
    * Zero-rated supplies are taxed at 0%. They are taxable supplies, so the
      input VAT on related purchases stays creditable.
    * Exempt supplies carry no VAT. A purchase marked ``EXEMPT`` carries no
      input VAT to claim.

    VAT is computed per invoice and rounded to the shilling, as it would be
    printed on the invoice. If input VAT exceeds output VAT the amount payable
    is zero, and the excess is reported in ``notes["credit_carried_forward"]``.
    """

    name = "VAT"

    RATES: dict[SupplyType, Decimal] = {
        SupplyType.ZERO_RATED: Decimal(0),
        SupplyType.EXEMPT: Decimal(0),
    }

    def __init__(self, standard_rate: Decimal = VAT_STANDARD_RATE) -> None:
        self.standard_rate = standard_rate

    def rate_for(self, supply_type: SupplyType) -> Decimal:
        """VAT rate for a supply type."""
        if supply_type is SupplyType.STANDARD:
            return self.standard_rate
        return self.RATES[supply_type]

    def invoice_vat(self, invoice: Invoice) -> Money:
        """VAT on one invoice, rounded to the shilling."""
        return (invoice.net_amount * self.rate_for(invoice.supply_type)).rounded()

    def _total(self, invoices: tuple[Invoice, ...], direction: InvoiceDirection) -> Money:
        return Money.sum(self.invoice_vat(i) for i in invoices if i.direction is direction)

    def output_vat(self, ctx: TaxContext) -> Money:
        """VAT charged on sales."""
        return self._total(ctx.invoices, InvoiceDirection.SALE)

    def input_vat(self, ctx: TaxContext) -> Money:
        """Creditable VAT paid on purchases."""
        return self._total(ctx.invoices, InvoiceDirection.PURCHASE)

    def calculate(self, ctx: TaxContext) -> TaxResult:
        """Net VAT payable for the invoices in ``ctx``."""
        lines = []
        for invoice in ctx.invoices:
            vat = self.invoice_vat(invoice)
            sign = vat if invoice.direction is InvoiceDirection.SALE else -vat
            label = "Output" if invoice.direction is InvoiceDirection.SALE else "Input"
            lines.append(
                ResultLine(
                    f"{label} {invoice.number} ({invoice.supply_type.value})",
                    invoice.net_amount,
                    format_rate(self.rate_for(invoice.supply_type)),
                    sign,
                )
            )
        output, input_ = self.output_vat(ctx), self.input_vat(ctx)
        net = output - input_
        sales = Money.sum(i.net_amount for i in ctx.invoices if i.direction is InvoiceDirection.SALE)
        notes = {
            "output_vat": output,
            "input_vat": input_,
            "net_vat": net,
            "credit_carried_forward": (-net).max_zero(),
        }
        result = self._result(sales, lines, schedule=f"VAT standard rate {format_rate(self.standard_rate)}", notes=notes)
        if net.is_negative():
            # A refund position: nothing is payable this period.
            result = replace(result, amount=Money.zero(), unrounded=Money.zero())
        return result
