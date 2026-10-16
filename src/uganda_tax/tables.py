"""Tabular views of tax results for display in notebooks."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from .context import TaxResult


def results_table(results: Iterable[TaxResult]) -> pd.DataFrame:
    """Breakdown lines of one or more results as a DataFrame (amounts in UGX, exact Decimals)."""
    rows = [
        {
            "Tax": result.tax,
            "Line": line.description,
            "Base (UGX)": line.base.amount,
            "Rate": line.rate,
            "Amount (UGX)": line.amount.amount,
        }
        for result in results
        for line in result.lines
    ]
    return pd.DataFrame(rows)
