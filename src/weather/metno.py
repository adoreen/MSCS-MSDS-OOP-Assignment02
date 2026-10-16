"""Second source: MET Norway Locationforecast 2.0 (``compact``), aggregated to daily values.

MET Norway's terms of service require an identifying ``User-Agent`` with
contact details, and ask clients to use at most 4 decimals of latitude and longitude.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pandas as pd

from .config import user_agent
from .exceptions import WeatherError
from .http import fetch_json

METNO_URL = "https://api.met.no/weatherapi/locationforecast/2.0/compact"


def get_metno_forecast(
    latitude: float,
    longitude: float,
    email: str,
    *,
    fetch: Callable[..., Any] = fetch_json,
) -> dict[str, Any]:
    """Request the compact Locationforecast for a point (coordinates truncated to 4 decimals)."""
    params = {"lat": round(latitude, 4), "lon": round(longitude, 4)}
    return fetch(METNO_URL, params, headers={"User-Agent": user_agent(email)})


def metno_to_hourly(payload: dict[str, Any]) -> pd.DataFrame:
    """Hourly (or coarser) rows: UTC time, temperature (°C), wind (m/s) and next-hour precipitation (mm)."""
    try:
        series = payload["properties"]["timeseries"]
    except (KeyError, TypeError) as exc:
        raise WeatherError("MET Norway payload has no properties.timeseries") from exc
    rows = []
    for step in series:
        details = step["data"]["instant"]["details"]
        next_1h = step["data"].get("next_1_hours", {}).get("details", {})
        next_6h = step["data"].get("next_6_hours", {}).get("details", {})
        rows.append(
            {
                "time": step["time"],
                "temperature": details.get("air_temperature"),
                "wind_speed": details.get("wind_speed"),
                "precip_1h": next_1h.get("precipitation_amount"),
                "precip_6h": next_6h.get("precipitation_amount"),
            }
        )
    frame = pd.DataFrame(rows)
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    return frame.set_index("time")


def metno_to_daily(payload: dict[str, Any], timezone: str = "UTC") -> pd.DataFrame:
    """Aggregate MET Norway data to daily values in the location's time zone.

    Precipitation: the 1-hour amounts are summed while hourly steps exist.
    Where the series switches to 6-hourly steps, the 6-hour amounts are used,
    so no hour is counted twice. Wind is converted from m/s to km/h so it can
    be compared with Open-Meteo.

    Only complete days are kept: the first (partial) local day is dropped when
    it has fewer than 6 data points.
    """
    hourly = metno_to_hourly(payload)
    local = hourly.tz_convert(timezone)
    step_hours = local.index.to_series().diff().shift(-1).dt.total_seconds().div(3600)
    precip = local["precip_1h"].where(step_hours.fillna(1) <= 1, local["precip_6h"])
    grouped = local.assign(precip=precip).groupby(local.index.date)
    daily = pd.DataFrame(
        {
            "Max temp (°C)": grouped["temperature"].max(),
            "Min temp (°C)": grouped["temperature"].min(),
            "Precipitation (mm)": grouped["precip"].sum(min_count=1),
            "Max wind (km/h)": grouped["wind_speed"].max() * 3.6,
            "Data points": grouped["temperature"].count(),
        }
    )
    daily.index = pd.to_datetime(daily.index)
    daily.index.name = "Date"
    if len(daily) and daily["Data points"].iloc[0] < 6:
        daily = daily.iloc[1:]
    return daily
