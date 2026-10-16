"""Charts for the tax notebook.

All tax arithmetic is done in ``Decimal``/``Money``. Values are converted to
``float`` only here, at the last moment, because matplotlib draws floats. No
converted value ever flows back into a calculation.
"""

from __future__ import annotations

from collections.abc import Sequence

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure

from .money import Money
from .planner import Comparison
from .schedules import ProgressiveSchedule

STYLES = ("-", "--", ":")
PAYROLL_COLOURS = {"Net pay": "#2e86ab", "PAYE": "#d1495b", "NSSF (employee)": "#edae49", "LST": "#66a182"}


def _to_plot(value: Money, scale: int = 1) -> float:
    """Money -> float in units of ``scale`` UGX, for drawing only."""
    return float(value.amount / scale)


def plot_paye_schedules(schedules: Sequence[tuple[ProgressiveSchedule, str]]) -> Figure:
    """Monthly PAYE up to 1 million UGX, and the effective rate up to 20 million UGX."""
    low = range(0, 1_000_001, 5_000)
    high = range(50_000, 20_000_001, 50_000)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.8))
    for (schedule, label), style in zip(schedules, STYLES):
        ax1.plot([x / 1_000 for x in low], [_to_plot(schedule.tax(Money(x)), 1_000) for x in low], style, label=label)
        rates = [float(schedule.tax(Money(x)).amount / x * 100) for x in high]
        ax2.plot([x / 1_000_000 for x in high], rates, style, label=label)
    for edge in (235, 335, 410, 485):
        ax1.axvline(edge, color="grey", lw=0.6, alpha=0.5)
    ax1.set(title="Monthly PAYE up to UGX 1 million", xlabel="Monthly chargeable income ('000 UGX)",
            ylabel="PAYE ('000 UGX)")
    ax2.axhline(40, color="grey", lw=0.6, ls="--")
    ax2.annotate("40% marginal rate above 10M", (12, 40.5), fontsize=8, color="grey")
    ax2.set(title="Effective PAYE rate", xlabel="Monthly chargeable income (million UGX)",
            ylabel="PAYE as % of income", ylim=(0, 45))
    for ax in (ax1, ax2):
        ax.grid(alpha=0.3)
        ax.legend()
    fig.suptitle("Uganda PAYE schedules (grey lines: band edges)")
    fig.tight_layout()
    return fig


def plot_payroll(payroll: pd.DataFrame, title: str) -> Figure:
    """Stacked bars splitting each employee's emoluments into net pay, PAYE, NSSF and LST."""
    columns = {"Net pay": "Net pay (UGX)", "PAYE": "PAYE (UGX)", "NSSF (employee)": "NSSF employee (UGX)",
               "LST": "LST (UGX)"}
    ordered = payroll.sort_values("Gross pay (UGX)")
    fig, ax = plt.subplots(figsize=(11, 5))
    bottom = [0.0] * len(ordered)
    for label, column in columns.items():
        values = [float(v / 1_000_000) for v in ordered[column]]
        ax.bar(ordered.index, values, bottom=bottom, label=label, color=PAYROLL_COLOURS[label])
        bottom = [b + v for b, v in zip(bottom, values)]
    for i, residency in enumerate(ordered["Residency"]):
        if residency == "non_resident":
            ax.annotate("non-res.", (i, bottom[i]), ha="center", va="bottom", fontsize=8)
    ax.set(title=title, xlabel="Employee (sorted by gross pay)", ylabel="Million UGX per month")
    ax.tick_params(axis="x", rotation=45)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    return fig


def plot_planner(sweep: Sequence[Comparison]) -> Figure:
    """Effective tax rate of both scenarios, and the salary scenario's cash advantage, against profit."""
    x = [_to_plot(c.first.profit, 1_000_000) for c in sweep]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 4.8))
    ax1.plot(x, [float(c.first.effective_tax_rate * 100) for c in sweep], label="Salary: PAYE + LST")
    ax1.plot(x, [float(c.second.effective_tax_rate * 100) for c in sweep], "--", label="Dividend: CIT 30% + WHT 15%")
    ax1.set(title="Total tax as % of annual profit", xlabel="Annual profit before owner pay (million UGX)",
            ylabel="Effective tax rate (%)", ylim=(0, 50))
    with_savings = [c.first.cash_to_owner + c.first.total_savings - c.second.cash_to_owner for c in sweep]
    cash_only = [c.first.cash_to_owner - c.second.cash_to_owner for c in sweep]
    ax2.plot(x, [_to_plot(v, 1_000_000) for v in with_savings], label="Salary (cash + NSSF) − dividend cash")
    ax2.plot(x, [_to_plot(v, 1_000_000) for v in cash_only], "--", label="Salary (cash only) − dividend cash")
    ax2.axhline(0, color="grey", lw=0.8)
    ax2.set(title="Advantage of salary over dividend", xlabel="Annual profit before owner pay (million UGX)",
            ylabel="Difference (million UGX per year)")
    for ax in (ax1, ax2):
        ax.grid(alpha=0.3)
        ax.legend()
    fig.tight_layout()
    return fig
