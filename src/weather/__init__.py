"""Mini-Project 1: geocoding and weather forecast client (Open-Meteo, MET Norway)."""

from .exceptions import (
    AmbiguousLocationError,
    ConfigurationError,
    InvalidCoordinatesError,
    LocationNotFoundError,
    WeatherAPIError,
    WeatherError,
)
from .config import contact_email, user_agent
from .forecast import describe_weather_code, forecast_to_dataframe, get_forecast, summarise
from .geocoding import Location, choose_location, geocode, parse_locations
from .http import RetryPolicy, fetch_json
from .metno import get_metno_forecast, metno_to_daily

__all__ = [
    "AmbiguousLocationError", "ConfigurationError", "InvalidCoordinatesError", "Location",
    "LocationNotFoundError", "RetryPolicy", "WeatherAPIError", "WeatherError", "choose_location",
    "contact_email", "describe_weather_code", "fetch_json", "forecast_to_dataframe", "geocode",
    "get_forecast", "get_metno_forecast", "metno_to_daily", "parse_locations",
    "summarise", "user_agent",
]
