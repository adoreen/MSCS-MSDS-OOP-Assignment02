"""Place name to coordinates with the Open-Meteo Geocoding API."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .exceptions import AmbiguousLocationError, LocationNotFoundError
from .http import fetch_json

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"


@dataclass(frozen=True)
class Location:
    """One geocoding candidate."""

    name: str
    latitude: float
    longitude: float
    country: str = ""
    admin1: str = ""
    timezone: str = "auto"
    population: int | None = None
    elevation: float | None = None

    @property
    def label(self) -> str:
        """Readable label, e.g. ``"Springfield, Illinois, United States (39.80, -89.64)"``."""
        parts = [p for p in (self.name, self.admin1, self.country) if p]
        return f"{', '.join(parts)} ({self.latitude:.2f}, {self.longitude:.2f})"


def parse_locations(payload: dict[str, Any]) -> list[Location]:
    """Convert a geocoding response into :class:`Location` objects.

    The ``results`` key is *absent* (not empty) when nothing matches, so it is
    read with ``.get``. Entries without coordinates are skipped.
    """
    locations = []
    for item in payload.get("results") or []:
        if "latitude" not in item or "longitude" not in item:
            continue
        locations.append(
            Location(
                name=item.get("name", "?"),
                latitude=float(item["latitude"]),
                longitude=float(item["longitude"]),
                country=item.get("country", ""),
                admin1=item.get("admin1", ""),
                timezone=item.get("timezone", "auto"),
                population=item.get("population"),
                elevation=item.get("elevation"),
            )
        )
    return locations


def geocode(
    name: str,
    count: int = 10,
    *,
    fetch: Callable[..., Any] = fetch_json,
) -> list[Location]:
    """Return candidate locations for ``name``, most relevant first.

    Raises:
        ValueError: if ``name`` is blank.
        LocationNotFoundError: if no place matches.
        WeatherAPIError: if the request fails.
    """
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("Location name must not be empty")
    payload = fetch(GEOCODING_URL, {"name": cleaned, "count": count, "language": "en", "format": "json"})
    locations = parse_locations(payload)
    if not locations:
        raise LocationNotFoundError(f"No place found for {cleaned!r}")
    return locations


def choose_location(
    candidates: list[Location],
    choice: int | None = None,
    *,
    interactive: bool = False,
    prompt: Callable[[str], str] = input,
) -> Location:
    """Pick one location from the candidates.

    * One candidate: it is returned.
    * ``choice`` given: that index is returned.
    * ``interactive=True``: the candidates are printed and the user is asked.
    * Otherwise: :class:`AmbiguousLocationError` lists the candidates.
    """
    if not candidates:
        raise LocationNotFoundError("No candidates to choose from")
    if len(candidates) == 1:
        return candidates[0]
    if choice is None and interactive:
        for index, candidate in enumerate(candidates):
            print(f"[{index}] {candidate.label}")
        choice = int(prompt(f"Choose 0-{len(candidates) - 1}: "))
    if choice is None:
        raise AmbiguousLocationError(candidates[0].name, candidates)
    if not 0 <= choice < len(candidates):
        raise IndexError(f"Choice {choice} is out of range 0-{len(candidates) - 1}")
    return candidates[choice]
