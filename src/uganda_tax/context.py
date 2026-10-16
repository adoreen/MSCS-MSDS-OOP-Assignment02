"""Input (:class:`TaxContext`) and output (:class:`TaxResult`) types for every tax.

A single immutable context carries all the facts a tax might need. Each
:class:`~uganda_tax.base.Tax` subclass reads only the fields it needs and
validates them, raising :class:`~uganda_tax.exceptions.InvalidIncomeError`
when a required field is missing or invalid. Using one context type (rather
than one subclass per tax) keeps ``Tax.calculate(ctx)`` substitutable: any tax
can be called with any context, and the payroll pipeline can pass the same
context through several taxes.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field, replace
from decimal import Decimal
from enum import Enum

from .exceptions import InvalidIncomeError, InvalidSupplyError
from .money import Money


class Residency(str, Enum):
    """Tax residency status of an individual or company."""

    RESIDENT = "resident"
    NON_RESIDENT = "non_resident"


class SupplyType(str, Enum):
    """VAT treatment of a supply."""

    STANDARD = "standard"  # taxable at the standard rate (18%)
    ZERO_RATED = "zero_rated"  # taxable at 0%; input VAT remains creditable
    EXEMPT = "exempt"  # outside VAT; no output VAT and no input credit


class InvoiceDirection(str, Enum):
    """Whether an invoice records a sale (output VAT) or a purchase (input VAT)."""

    SALE = "sale"
    PURCHASE = "purchase"


@dataclass(frozen=True)
class Invoice:
    """A VAT invoice, with its value stated exclusive of VAT."""

    number: str
    net_amount: Money
    supply_type: SupplyType
    direction: InvoiceDirection = InvoiceDirection.SALE
    description: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.net_amount, Money):
            raise InvalidSupplyError(f"Invoice {self.number}: net_amount must be Money")
        if self.net_amount.is_negative():
            raise InvalidSupplyError(
                f"Invoice {self.number}: net amount cannot be negative ({self.net_amount})"
            )
        if not isinstance(self.supply_type, SupplyType):
            raise InvalidSupplyError(
                f"Invoice {self.number}: unknown supply type {self.supply_type!r}"
            )
        if not isinstance(self.direction, InvoiceDirection):
            raise InvalidSupplyError(
                f"Invoice {self.number}: unknown direction {self.direction!r}"
            )


@dataclass(frozen=True)
class Deduction:
    """An allowable deduction claimed against company revenue."""

    description: str
    amount: Money

    def __post_init__(self) -> None:
        if not isinstance(self.amount, Money) or self.amount.is_negative():
            raise InvalidIncomeError(
                f"Deduction {self.description!r} must be a non-negative Money amount"
            )


@dataclass(frozen=True)
class TaxContext:
    """The facts a tax calculation needs.

    Attributes:
        on: The date the liability arises; it selects the schedule in force.
        residency: Residency status of the taxpayer.
        gross_pay: Monthly gross (basic) pay of an employee.
        allowances: Monthly taxable allowances (housing, transport, ...).
        pre_paye_deductions: Amounts deducted from emoluments before PAYE
            (Local Service Tax, set by the payroll pipeline).
        invoices: VAT invoices for the period.
        revenue: Company revenue (gross income) for the year of income.
        deductions: Allowable company deductions for the year of income.
        dividends: Dividend amount paid (used by the withholding-tax planner).
    """

    on: dt.date
    residency: Residency = Residency.RESIDENT
    gross_pay: Money | None = None
    allowances: Money = field(default_factory=Money.zero)
    pre_paye_deductions: Money = field(default_factory=Money.zero)
    invoices: tuple[Invoice, ...] = ()
    revenue: Money | None = None
    deductions: tuple[Deduction, ...] = ()
    dividends: Money | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.on, dt.date):
            raise TypeError("TaxContext.on must be a datetime.date")
        if not isinstance(self.residency, Residency):
            raise TypeError("TaxContext.residency must be a Residency")
        for name in ("gross_pay", "allowances", "pre_paye_deductions", "revenue", "dividends"):
            value = getattr(self, name)
            if value is None:
                continue
            if not isinstance(value, Money):
                raise InvalidIncomeError(f"{name} must be Money, got {type(value).__name__}")
            if value.is_negative():
                raise InvalidIncomeError(f"{name} cannot be negative ({value})")
        # Accept lists for convenience but store tuples so the context stays immutable.
        object.__setattr__(self, "invoices", tuple(self.invoices))
        object.__setattr__(self, "deductions", tuple(self.deductions))

    @property
    def employment_income(self) -> Money:
        """Monthly gross pay plus taxable allowances.

        Raises:
            InvalidIncomeError: if no gross pay was supplied.
        """
        if self.gross_pay is None:
            raise InvalidIncomeError("gross_pay is required for employment taxes")
        return self.gross_pay + self.allowances

    def with_changes(self, **changes: object) -> TaxContext:
        """Return a copy with some fields replaced (the context itself is immutable)."""
        return replace(self, **changes)  # type: ignore[arg-type]


@dataclass(frozen=True)
class ResultLine:
    """One line of a calculation breakdown, e.g. a single PAYE band."""

    description: str
    base: Money
    rate: str
    amount: Money


@dataclass(frozen=True)
class TaxResult:
    """The outcome of one tax calculation.

    Attributes:
        tax: Name of the tax (e.g. ``"PAYE"``).
        amount: Liability, rounded according to the money rounding rule.
        unrounded: The exact liability before rounding.
        base: The amount the tax was charged on.
        lines: Step-by-step breakdown.
        schedule: Name/version of the rate schedule used.
        notes: Extra figures (e.g. employer NSSF, VAT credit carried forward).
    """

    tax: str
    amount: Money
    unrounded: Money
    base: Money
    lines: tuple[ResultLine, ...] = ()
    schedule: str = ""
    notes: dict[str, Money] = field(default_factory=dict)

    @property
    def effective_rate(self) -> Decimal:
        """Liability divided by base (0 when the base is zero)."""
        if not self.base:
            return Decimal(0)
        return self.unrounded.amount / self.base.amount

    def __str__(self) -> str:
        parts = [f"{self.tax}: {self.amount} on base {self.base}"]
        if self.schedule:
            parts.append(f"[{self.schedule}]")
        return " ".join(parts)

