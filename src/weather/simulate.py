"""Simulated failures for demonstrating the robustness of :func:`weather.http.fetch_json`."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import requests

from .exceptions import WeatherError


class FlakySession(requests.Session):
    """Answers the first ``failures`` GET requests with a simulated HTTP 503, then behaves normally."""

    def __init__(self, failures: int) -> None:
        super().__init__()
        self.failures = failures
        self.calls = 0

    def get(self, url: str | bytes, **kwargs: Any) -> requests.Response:  # type: ignore[override]
        self.calls += 1
        if self.calls <= self.failures:
            fake = requests.Response()
            fake.status_code, fake.reason, fake.url = 503, "Service Unavailable", str(url)
            fake._content = b'{"reason": "simulated outage"}'
            return fake
        return super().get(url, **kwargs)


class OfflineSession(requests.Session):
    """Simulates having no network: every request fails before leaving the machine."""

    def send(self, request: requests.PreparedRequest, **kwargs: Any) -> requests.Response:  # type: ignore[override]
        raise requests.ConnectionError("Simulated: network is unreachable")


def run_demo(label: str, action: Callable[[], Any]) -> str:
    """Run ``action`` and describe its result or the error it raised (for notebook demos)."""
    start = time.perf_counter()
    try:
        outcome = f"OK -> {type(action()).__name__}"
    except (WeatherError, ValueError) as exc:
        outcome = f"{type(exc).__name__}: {exc}"
    return f"{label}\n    {outcome}\n    ({time.perf_counter() - start:.2f} s)\n"
