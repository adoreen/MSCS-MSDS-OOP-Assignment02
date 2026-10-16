"""Re-capture the sample API responses used by the offline tests (tests/fixtures/weather/).

Usage (one request per file, so traffic stays low):

    CONTACT_EMAIL=b38632@students.ucu.ac.ug python scripts/capture_fixtures.py

The contact email is required, because both providers must be able to identify the client.
"""

from __future__ import annotations

import json
from pathlib import Path

import requests

from weather.config import contact_email, user_agent
from weather.forecast import DAILY_VARIABLES, FORECAST_URL
from weather.geocoding import GEOCODING_URL
from weather.http import fetch_json
from weather.metno import get_metno_forecast

OUT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "weather"


def save(name: str, payload: object) -> None:
    """Write ``payload`` as pretty JSON to the fixtures folder."""
    (OUT / name).write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    print("saved", name)


def main() -> None:
    """Fetch and save every fixture."""
    email = contact_email()
    headers = {"User-Agent": user_agent(email)}

    def geocode_raw(name: str, count: int) -> dict:
        return fetch_json(GEOCODING_URL, {"name": name, "count": count, "language": "en", "format": "json"},
                          headers=headers)

    save("geocode_dresden.json", geocode_raw("Dresden", 5))
    save("geocode_springfield.json", geocode_raw("Springfield", 10))
    save("geocode_no_results.json", geocode_raw("Xqzzyplat", 10))

    dresden = json.loads((OUT / "geocode_dresden.json").read_text(encoding="utf-8"))["results"][0]
    lat, lon = dresden["latitude"], dresden["longitude"]
    save("forecast_dresden.json", fetch_json(
        FORECAST_URL,
        {"latitude": lat, "longitude": lon, "daily": ",".join(DAILY_VARIABLES), "timezone": "auto",
         "forecast_days": 7},
        headers=headers,
    ))
    # A 400 response is the point here, so it is fetched without the raising wrapper.
    bad = requests.get(FORECAST_URL, params={"latitude": 999, "longitude": lon, "daily": "temperature_2m_max"},
                       headers=headers, timeout=10)
    save("forecast_invalid_latitude.json", bad.json())
    save("metno_dresden.json", get_metno_forecast(lat, lon, email))


if __name__ == "__main__":
    main()
