"""Daily forecast from the Open-Meteo Forecast API, as a pandas DataFrame."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pandas as pd

from .exceptions import InvalidCoordinatesError, WeatherError
from .geocoding import Location
from .http import fetch_json

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

DAILY_VARIABLES = (
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "wind_speed_10m_max",
)

#: Readable column names (units are appended from the response's ``daily_units``).
COLUMN_NAMES = {
    "temperature_2m_max": "Max temp",
    "temperature_2m_min": "Min temp",
    "precipitation_sum": "Precipitation",
    "wind_speed_10m_max": "Max wind",
}

#: WMO weather interpretation codes, from the Open-Meteo documentation
#: (https://open-meteo.com/en/docs, section "WMO Weather interpretation codes").
WMO_CODES: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def describe_weather_code(code: int | float | None) -> str:
    """Readable description of a WMO weather code (``"Unknown (code)"`` if unmapped)."""
    if code is None or pd.isna(code):
        return "No data"
    code = int(code)
    return WMO_CODES.get(code, f"Unknown ({code})")


def validate_request(latitude: float, longitude: float, days: int) -> None:
    """Check coordinates and forecast length before sending a request.

    Raises:
        InvalidCoordinatesError: if a value is out of range.
    """
    if not -90 <= latitude <= 90:
        raise InvalidCoordinatesError(f"Latitude must be in [-90, 90], got {latitude}")
    if not -180 <= longitude <= 180:
        raise InvalidCoordinatesError(f"Longitude must be in [-180, 180], got {longitude}")
    if not 1 <= days <= 16:
        raise InvalidCoordinatesError(f"Open-Meteo provides 1-16 forecast days, got {days}")


def get_forecast(
    latitude: float,
    longitude: float,
    days: int = 7,
    *,
    timezone: str = "auto",
    validate: bool = True,
    fetch: Callable[..., Any] = fetch_json,
) -> dict[str, Any]:
    """Request a daily forecast and return the raw JSON.

    ``timezone="auto"`` makes Open-Meteo use the location's own time zone, so
    the dates are local dates at the location.

    Args:
        validate: Check inputs locally first. Set ``False`` to see the server's
            own validation (used in the robustness demo).
    """
    if validate:
        validate_request(latitude, longitude, days)
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": ",".join(DAILY_VARIABLES),
        "timezone": timezone,
        "forecast_days": days,
    }
    return fetch(FORECAST_URL, params)


def forecast_to_dataframe(payload: dict[str, Any]) -> pd.DataFrame:
    """Turn an Open-Meteo daily forecast into a tidy DataFrame.

    Columns: ``Date`` (index), ``Weather``, ``Weather code`` and one column per
    variable, with its unit in the name, e.g. ``"Max temp (°C)"``.

    Raises:
        WeatherError: if the payload has no ``daily`` block or misses a variable.
    """
    daily = payload.get("daily")
    if not isinstance(daily, dict) or "time" not in daily:
        raise WeatherError("Forecast payload has no 'daily' data")
    units = payload.get("daily_units", {})
    missing = [v for v in COLUMN_NAMES if v not in daily]
    if missing:
        raise WeatherError(f"Forecast payload is missing {missing}")

    frame = pd.DataFrame({"Date": pd.to_datetime(daily["time"])})
    codes = daily.get("weather_code", [None] * len(frame))
    frame["Weather"] = [describe_weather_code(c) for c in codes]
    for variable, label in COLUMN_NAMES.items():
        unit = units.get(variable, "")
        frame[f"{label} ({unit})" if unit else label] = pd.to_numeric(daily[variable])
    frame["Weather code"] = pd.array(codes, dtype="Int64")
    return frame.set_index("Date")


def column(frame: pd.DataFrame, label: str) -> str:
    """Find the full column name that starts with ``label`` (e.g. ``"Max temp"``)."""
    for name in frame.columns:
        if name.startswith(label):
            return name
    raise KeyError(label)


def summarise(frame: pd.DataFrame, location: Location | str) -> str:
    """A short plain-English summary of a forecast DataFrame."""
    place = location.label if isinstance(location, Location) else location
    tmax, tmin = frame[column(frame, "Max temp")], frame[column(frame, "Min temp")]
    rain, wind = frame[column(frame, "Precipitation")], frame[column(frame, "Max wind")]
    wettest = rain.idxmax()
    windiest = wind.idxmax()
    common = frame["Weather"].mode().iloc[0]
    rainy_days = int((rain >= 1.0).sum())
    return (
        f"Forecast for {place}, {frame.index[0]:%a %d %b} to {frame.index[-1]:%a %d %b}: "
        f"highs {tmax.min():.0f} to {tmax.max():.0f} °C, lows {tmin.min():.0f} to {tmin.max():.0f} °C. "
        f"{rainy_days} of {len(frame)} days with at least 1 mm of rain; wettest {wettest:%a %d %b} "
        f"({rain.max():.1f} mm). Windiest {windiest:%a %d %b} ({wind.max():.0f} km/h). "
        f"Most common conditions: {common.lower()}. Data: Open-Meteo.com (CC BY 4.0)."
    )
