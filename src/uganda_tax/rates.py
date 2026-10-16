"""Statutory rates used by the engine, with their sources and effective dates.

Sources (checked 16 October 2026)
---------------------------------
* PAYE, FY 2026/27 resident and non-resident tables: URA "PAYE rates" page,
  https://ura.go.ug/?p=16453, implementing the Income Tax (Amendment) Act 2026
  (in force 1 July 2026). The resident table matches the assignment brief.
* PAYE, FY 2025/26 resident table (nil band up to 235,000): the schedule in force
  before 1 July 2026, as summarised at
  https://afrotools.com/fr/blog/uganda-paye-tax-2026-27/. Earlier years are not modelled.
* Local Service Tax: Local Governments (Amendment) (No. 2) Act 2008 (Cap. 243),
  ten bands from UGX 5,000 to 100,000 a year by monthly gross income, as tabulated
  in KCCA's "Local Service Tax (Assessment & Payment)" FAQ, February 2017
  (https://kcca.go.ug/uDocs/Local_Service_Tax_FAQs.pdf), which also states that
  LST is deducted from gross income before PAYE. It is collected in the first
  four months of the financial year (July to October).
* NSSF: 5% employee, 10% employer (NSSF Act, Cap. 230).
* VAT 18% (VAT Act); corporate income tax 30% for resident companies (Income Tax Act).
* Withholding tax on dividends: 15% for dividends paid to resident persons by
  unlisted companies (10% applies to individuals receiving dividends from
  companies listed on the Uganda Securities Exchange). Source: PwC Worldwide Tax
  Summaries, Uganda, "Withholding taxes" (reviewed January 2026),
  https://taxsummaries.pwc.com/uganda/corporate/withholding-taxes

Anything the engine is asked to compute for a date outside these ranges raises
:class:`~uganda_tax.exceptions.NoScheduleForDateError` instead of guessing.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from .money import Money
from .schedules import Band, ProgressiveSchedule, ScheduleRegistry, StepRow, StepSchedule

FY2025_START = dt.date(2025, 7, 1)
FY2026_START = dt.date(2026, 7, 1)
FY2025_END = FY2026_START - dt.timedelta(days=1)

_SURCHARGE_THRESHOLD = Money(10_000_000)
_SURCHARGE_RATE = Decimal("0.10")


def _bands(*spec: tuple[int, int | None, str]) -> tuple[Band, ...]:
    """Build bands from ``(lower, upper, rate)`` tuples."""
    return tuple(
        Band(Money(lower), None if upper is None else Money(upper), Decimal(rate))
        for lower, upper, rate in spec
    )


PAYE_RESIDENT_FY2025 = ProgressiveSchedule(
    name="PAYE resident FY2025/26",
    effective_from=FY2025_START,
    effective_to=FY2025_END,
    bands=_bands(
        (0, 235_000, "0"),
        (235_000, 335_000, "0.10"),
        (335_000, 410_000, "0.20"),
        (410_000, None, "0.30"),
    ),
    surcharge_threshold=_SURCHARGE_THRESHOLD,
    surcharge_rate=_SURCHARGE_RATE,
    source="Pre-amendment resident schedule (in force until 30 June 2026)",
)

PAYE_RESIDENT_FY2026 = ProgressiveSchedule(
    name="PAYE resident FY2026/27",
    effective_from=FY2026_START,
    effective_to=None,
    bands=_bands(
        (0, 335_000, "0"),
        (335_000, 410_000, "0.20"),
        (410_000, 485_000, "0.25"),
        (485_000, None, "0.30"),
    ),
    surcharge_threshold=_SURCHARGE_THRESHOLD,
    surcharge_rate=_SURCHARGE_RATE,
    source="URA PAYE rates (Income Tax (Amendment) Act 2026), https://ura.go.ug/?p=16453",
)

PAYE_NON_RESIDENT = ProgressiveSchedule(
    name="PAYE non-resident FY2025/26 onwards",
    effective_from=FY2025_START,
    effective_to=None,
    bands=_bands(
        (0, 335_000, "0.10"),
        (335_000, 410_000, "0.20"),
        (410_000, None, "0.30"),
    ),
    surcharge_threshold=_SURCHARGE_THRESHOLD,
    surcharge_rate=_SURCHARGE_RATE,
    source="URA PAYE rates, https://ura.go.ug/?p=16453",
)


def default_paye_registries() -> dict[str, ScheduleRegistry[ProgressiveSchedule]]:
    """Registries of PAYE schedules keyed by residency value."""
    return {
        "resident": ScheduleRegistry("PAYE (resident)", [PAYE_RESIDENT_FY2025, PAYE_RESIDENT_FY2026]),
        "non_resident": ScheduleRegistry("PAYE (non-resident)", [PAYE_NON_RESIDENT]),
    }


def _lst_rows(*spec: tuple[int, int | None, int]) -> tuple[StepRow, ...]:
    return tuple(
        StepRow(Money(lower), None if upper is None else Money(upper), Money(amount))
        for lower, upper, amount in spec
    )


LST_SCHEDULE = StepSchedule(
    name="Local Service Tax (Local Governments (Amendment) (No. 2) Act 2008)",
    effective_from=FY2025_START,
    effective_to=None,
    rows=_lst_rows(
        (100_000, 200_000, 5_000),
        (200_000, 300_000, 10_000),
        (300_000, 400_000, 20_000),
        (400_000, 500_000, 30_000),
        (500_000, 600_000, 40_000),
        (600_000, 700_000, 60_000),
        (700_000, 800_000, 70_000),
        (800_000, 900_000, 80_000),
        (900_000, 1_000_000, 90_000),
        (1_000_000, None, 100_000),
    ),
    source="KCCA LST FAQ (Feb 2017), Table 1: annual LST by monthly gross income",
)

NSSF_EMPLOYEE_RATE = Decimal("0.05")
NSSF_EMPLOYER_RATE = Decimal("0.10")
VAT_STANDARD_RATE = Decimal("0.18")
CIT_RATE = Decimal("0.30")
DIVIDEND_WHT_RATE = Decimal("0.15")
