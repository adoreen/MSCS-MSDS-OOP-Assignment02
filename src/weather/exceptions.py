"""Exceptions raised by the weather client."""

from __future__ import annotations


class WeatherError(Exception):
    """Base class for all weather-client errors."""


class WeatherAPIError(WeatherError):
    """A request failed for good: a non-retryable HTTP error, or all retries used up.

    Attributes:
        url: The URL requested (without query string).
        attempts: Number of attempts made.
        status: Last HTTP status code, if a response was received.
        reason: Server-supplied error text, if any.
    """

    def __init__(
        self,
        message: str,
        *,
        url: str,
        attempts: int,
        status: int | None = None,
        reason: str | None = None,
    ) -> None:
        self.url = url
        self.attempts = attempts
        self.status = status
        self.reason = reason
        details = [f"url={url}", f"attempts={attempts}"]
        if status is not None:
            details.append(f"status={status}")
        if reason:
            details.append(f"reason={reason!r}")
        super().__init__(f"{message} ({', '.join(details)})")


class LocationNotFoundError(WeatherError, LookupError):
    """The geocoder returned no candidates for a place name."""


class AmbiguousLocationError(WeatherError):
    """Several places match a name and no choice was supplied."""

    def __init__(self, name: str, candidates: list) -> None:  # list[Location]
        self.name = name
        self.candidates = candidates
        listing = "; ".join(f"[{i}] {c.label}" for i, c in enumerate(candidates))
        super().__init__(f"{len(candidates)} places match {name!r}: {listing}")


class InvalidCoordinatesError(WeatherError, ValueError):
    """Latitude, longitude or forecast length outside the valid range."""


class ConfigurationError(WeatherError):
    """Missing or invalid configuration, such as the contact email."""
