"""Offline tests for the weather client, using saved JSON responses in tests/fixtures/weather."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
import requests

from weather import (
    AmbiguousLocationError,
    ConfigurationError,
    InvalidCoordinatesError,
    LocationNotFoundError,
    RetryPolicy,
    WeatherAPIError,
    choose_location,
    contact_email,
    describe_weather_code,
    fetch_json,
    forecast_to_dataframe,
    geocode,
    get_forecast,
    metno_to_daily,
    parse_locations,
    summarise,
    user_agent,
)

FIXTURES = Path(__file__).parent / "fixtures" / "weather"


def load(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def fake_fetch(payload: dict[str, Any]):
    """A stand-in for fetch_json that records its arguments and returns ``payload``."""
    calls: list[tuple] = []

    def fetch(url: str, params: dict | None = None, **kwargs: Any) -> dict[str, Any]:
        calls.append((url, params, kwargs))
        return payload

    fetch.calls = calls  # type: ignore[attr-defined]
    return fetch


# ----- geocoding --------------------------------------------------------------------
def test_parse_locations_single_city() -> None:
    locations = parse_locations(load("geocode_dresden.json"))
    assert locations[0].name == "Dresden"
    assert locations[0].country == "Germany"
    assert locations[0].timezone == "Europe/Berlin"
    assert 50 < locations[0].latitude < 52


def test_parse_locations_missing_results_key() -> None:
    payload = load("geocode_no_results.json")
    assert "results" not in payload  # the API omits the key rather than sending []
    assert parse_locations(payload) == []


def test_geocode_raises_when_nothing_found() -> None:
    with pytest.raises(LocationNotFoundError):
        geocode("Xqzzyplat", fetch=fake_fetch(load("geocode_no_results.json")))


def test_geocode_rejects_blank_name() -> None:
    with pytest.raises(ValueError):
        geocode("   ", fetch=fake_fetch({}))


def test_ambiguous_name_lists_candidates_and_allows_choice() -> None:
    candidates = geocode("Springfield", fetch=fake_fetch(load("geocode_springfield.json")))
    assert len(candidates) > 1
    with pytest.raises(AmbiguousLocationError) as info:
        choose_location(candidates)
    assert "Illinois" in str(info.value)
    assert choose_location(candidates, 1).admin1 == "Illinois"
    picked = choose_location(candidates, interactive=True, prompt=lambda _: "2")
    assert picked.admin1 == "Massachusetts"
    with pytest.raises(IndexError):
        choose_location(candidates, 99)


# ----- forecast ---------------------------------------------------------------------
def test_forecast_dataframe_columns_and_units() -> None:
    frame = forecast_to_dataframe(load("forecast_dresden.json"))
    assert list(frame.columns) == [
        "Weather", "Max temp (°C)", "Min temp (°C)", "Precipitation (mm)", "Max wind (km/h)", "Weather code"
    ]
    assert isinstance(frame.index, pd.DatetimeIndex)
    assert len(frame) == 7
    assert (frame["Max temp (°C)"] >= frame["Min temp (°C)"]).all()
    payload = load("forecast_dresden.json")
    first_day = pd.Timestamp(payload["daily"]["time"][0])
    assert frame.loc[first_day, "Max temp (°C)"] == pytest.approx(payload["daily"]["temperature_2m_max"][0])


def test_weather_code_decoding() -> None:
    payload = load("forecast_dresden.json")
    frame = forecast_to_dataframe(payload)
    expected = [describe_weather_code(c) for c in payload["daily"]["weather_code"]]
    assert list(frame["Weather"]) == expected
    assert not any(text.startswith("Unknown") for text in expected)
    assert describe_weather_code(45) == "Fog"
    assert describe_weather_code(0) == "Clear sky"
    assert describe_weather_code(95) == "Thunderstorm"
    assert describe_weather_code(42) == "Unknown (42)"
    assert describe_weather_code(None) == "No data"


def test_forecast_dataframe_rejects_bad_payload() -> None:
    from weather import WeatherError

    with pytest.raises(WeatherError):
        forecast_to_dataframe(load("forecast_invalid_latitude.json"))


def test_summary_mentions_place_and_source() -> None:
    text = summarise(forecast_to_dataframe(load("forecast_dresden.json")), "Dresden")
    assert "Dresden" in text and "Open-Meteo" in text and "°C" in text


def test_get_forecast_validates_and_builds_params() -> None:
    fetch = fake_fetch(load("forecast_dresden.json"))
    get_forecast(51.05, 13.74, 7, fetch=fetch)
    url, params, _ = fetch.calls[0]
    assert params["timezone"] == "auto"
    assert "temperature_2m_max" in params["daily"] and "wind_speed_10m_max" in params["daily"]
    with pytest.raises(InvalidCoordinatesError):
        get_forecast(999, 13.74, fetch=fetch)
    with pytest.raises(InvalidCoordinatesError):
        get_forecast(51.05, 13.74, days=30, fetch=fetch)


# ----- MET Norway -------------------------------------------------------------------
def test_metno_daily_aggregation() -> None:
    daily = metno_to_daily(load("metno_dresden.json"), "Europe/Berlin")
    assert {"Max temp (°C)", "Min temp (°C)", "Precipitation (mm)", "Max wind (km/h)"} <= set(daily.columns)
    assert (daily["Max temp (°C)"] >= daily["Min temp (°C)"]).all()
    assert (daily["Precipitation (mm)"].dropna() >= 0).all()
    assert daily.index.is_monotonic_increasing


def test_contact_email_comes_from_config_or_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CONTACT_EMAIL", raising=False)
    with pytest.raises(ConfigurationError):
        contact_email()
    with pytest.raises(ConfigurationError):
        contact_email("not-an-email")
    monkeypatch.setenv("CONTACT_EMAIL", "student@uni.ac.ug")
    assert contact_email() == "student@uni.ac.ug"
    assert user_agent("student@uni.ac.ug").endswith("(student@uni.ac.ug)")


# ----- robust HTTP ------------------------------------------------------------------
class FakeResponse:
    def __init__(self, status: int, body: Any = None) -> None:
        self.status_code = status
        self._body = body if body is not None else {}
        self.text = json.dumps(self._body)

    def json(self) -> Any:
        return self._body

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error", response=self)  # type: ignore[arg-type]


class FakeSession:
    """Returns (or raises) the queued outcomes in order."""

    def __init__(self, *outcomes: Any) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    def get(self, *args: Any, **kwargs: Any) -> FakeResponse:
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def test_retries_on_5xx_then_succeeds() -> None:
    session = FakeSession(FakeResponse(503), FakeResponse(502), FakeResponse(200, {"ok": True}))
    waits: list[float] = []
    assert fetch_json("https://x.test", session=session, sleep=waits.append) == {"ok": True}  # type: ignore[arg-type]
    assert session.calls == 3
    assert waits == [0.5, 1.0]  # exponential backoff


def test_gives_up_with_custom_exception() -> None:
    session = FakeSession(*[requests.ConnectionError("no network")] * 3)
    policy = RetryPolicy(max_attempts=3, backoff_base=1, backoff_cap=1.5)
    waits: list[float] = []
    with pytest.raises(WeatherAPIError) as info:
        fetch_json("https://x.test", session=session, policy=policy, sleep=waits.append)  # type: ignore[arg-type]
    assert info.value.attempts == 3
    assert waits == [1, 1.5]  # capped
    assert isinstance(info.value.__cause__, requests.ConnectionError)


def test_client_error_is_not_retried() -> None:
    session = FakeSession(FakeResponse(400, load("forecast_invalid_latitude.json")))
    with pytest.raises(WeatherAPIError) as info:
        fetch_json("https://x.test", session=session, sleep=lambda _: None)  # type: ignore[arg-type]
    assert session.calls == 1
    assert info.value.status == 400
    assert "Latitude must be in range" in (info.value.reason or "")
