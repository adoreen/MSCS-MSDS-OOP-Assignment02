"""Mini-Project 2: extensible Uganda tax engine (PAYE, NSSF, LST, VAT, CIT)."""

from .base import Tax
from .cit import CorporateIncomeTax, DividendWithholdingTax
from .context import (
    Deduction,
    Invoice,
    InvoiceDirection,
    Residency,
    ResultLine,
    SupplyType,
    TaxContext,
    TaxResult,
)
from .exceptions import (
    CurrencyMismatchError,
    InvalidIncomeError,
    InvalidSupplyError,
    NoScheduleForDateError,
    ScheduleConfigurationError,
    TaxError,
)
from .lst import LocalServiceTax
from .money import Money
from .nssf import NSSF
from .paye import PAYE
from .payroll import PayrollPipeline, Payslip
from .planner import DividendScenario, SalaryScenario, Scenario, TaxPlanner
from .schedules import Band, ProgressiveSchedule, ScheduleRegistry
from .vat import VAT

__all__ = [
    "Band", "CorporateIncomeTax", "CurrencyMismatchError", "Deduction", "DividendScenario",
    "DividendWithholdingTax", "InvalidIncomeError", "InvalidSupplyError", "Invoice",
    "InvoiceDirection", "LocalServiceTax", "Money", "NSSF", "NoScheduleForDateError", "PAYE",
    "PayrollPipeline", "Payslip", "ProgressiveSchedule", "Residency", "ResultLine",
    "SalaryScenario", "Scenario", "ScheduleConfigurationError", "ScheduleRegistry",
    "SupplyType", "Tax", "TaxContext", "TaxError", "TaxPlanner", "TaxResult", "VAT",
]
