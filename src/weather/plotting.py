"""Charts for the forecast notebook."""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure

from .forecast import column

TEMP_COLOUR = "#d1495b"
LOW_COLOUR = "#2e86ab"
RAIN_COLOUR = "#7fb7be"


def plot_forecast(frame: pd.DataFrame, title: str, source: str = "Open-Meteo.com (CC BY 4.0)") -> Figure:
    """Daily temperature range (band plus max/min lines) with precipitation bars on a second axis."""
    tmax, tmin = frame[column(frame, "Max temp")], frame[column(frame, "Min temp")]
    rain = frame[column(frame, "Precipitation")]

    fig, ax_temp = plt.subplots(figsize=(10, 5))
    ax_rain = ax_temp.twinx()
    ax_temp.set_zorder(ax_rain.get_zorder() + 1)  # draw temperature lines over the bars
    ax_temp.patch.set_visible(False)

    bars = ax_rain.bar(frame.index, rain, width=0.6, color=RAIN_COLOUR, alpha=0.6, label="Precipitation (mm)")
    band = ax_temp.fill_between(frame.index, tmin, tmax, color=TEMP_COLOUR, alpha=0.12, label="Daily range")
    (line_max,) = ax_temp.plot(frame.index, tmax, "o-", color=TEMP_COLOUR, label="Max temp (°C)")
    (line_min,) = ax_temp.plot(frame.index, tmin, "o-", color=LOW_COLOUR, label="Min temp (°C)")

    ax_temp.set_ylabel("Temperature (°C)")
    ax_rain.set_ylabel("Precipitation (mm)")
    ax_rain.set_ylim(0, max(5.0, float(rain.max()) * 2.5))  # keep bars in the lower part
    ax_temp.set_xlabel("Date (local time)")
    ax_temp.set_title(title)
    ax_temp.grid(alpha=0.3)
    ax_temp.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%a\n%d %b"))
    ax_temp.legend(handles=[line_max, line_min, band, bars], loc="upper left", fontsize=9)
    fig.text(0.99, 0.01, f"Source: {source}", ha="right", fontsize=8, color="grey")
    fig.tight_layout()
    return fig


def plot_comparison(first: pd.DataFrame, second: pd.DataFrame, labels: tuple[str, str], title: str) -> Figure:
    """Max/min temperature from two sources on the same axes."""
    fig, ax = plt.subplots(figsize=(10, 5))
    for frame, label, style in ((first, labels[0], "-"), (second, labels[1], "--")):
        ax.plot(frame.index, frame[column(frame, "Max temp")], style, marker="o", color=TEMP_COLOUR,
                label=f"{label}: max (°C)")
        ax.plot(frame.index, frame[column(frame, "Min temp")], style, marker="s", color=LOW_COLOUR,
                label=f"{label}: min (°C)")
    ax.set_xlabel("Date (local time)")
    ax.set_ylabel("Temperature (°C)")
    ax.set_title(title)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=9, ncol=2)
    ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%a\n%d %b"))
    fig.text(0.99, 0.01, f"Sources: {labels[0]}, {labels[1]} (both CC BY 4.0)", ha="right", fontsize=8, color="grey")
    fig.tight_layout()
    return fig
