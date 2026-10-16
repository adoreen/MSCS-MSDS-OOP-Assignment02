"""Robust JSON-over-HTTP helper: timeout, raise_for_status, retries with exponential backoff.

Every request in the project goes through :func:`fetch_json`.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import requests

from .config import APP_NAME
from .exceptions import WeatherAPIError

log = logging.getLogger(__name__)

#: Statuses worth retrying: rate limiting and server-side errors.
RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})


@dataclass(frozen=True)
class RetryPolicy:
    """How many times to retry and how long to wait.

    The wait before retry ``n`` (``n = 1, 2, ...``) is
    ``min(backoff_base * 2 ** (n - 1), backoff_cap)`` seconds.
    """

    max_attempts: int = 4
    backoff_base: float = 0.5
    backoff_cap: float = 8.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.backoff_base < 0 or self.backoff_cap < 0:
            raise ValueError("backoff values must be non-negative")

    def delay(self, retry_number: int) -> float:
        """Seconds to wait before retry number ``retry_number`` (1-based)."""
        return min(self.backoff_base * 2 ** (retry_number - 1), self.backoff_cap)


DEFAULT_POLICY = RetryPolicy()
DEFAULT_TIMEOUT = 10.0
DEFAULT_USER_AGENT = APP_NAME  # fallback only; callers pass a User-Agent with the contact email


def _server_reason(response: requests.Response) -> str | None:
    """Extract an error message from a JSON error body (Open-Meteo uses ``{"reason": ...}``)."""
    try:
        body = response.json()
    except ValueError:
        return response.text[:200] or None
    if isinstance(body, dict):
        return body.get("reason") or body.get("message") or body.get("error_description")
    return None


def _short(error: Exception | None, limit: int = 160) -> str:
    """A one-line, length-limited description of ``error`` for error messages."""
    text = " ".join(str(error).split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def fetch_json(
    url: str,
    params: Mapping[str, Any] | None = None,
    *,
    headers: Mapping[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    policy: RetryPolicy = DEFAULT_POLICY,
    session: requests.Session | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    """GET ``url`` and return the decoded JSON body.

    * Every attempt uses ``timeout`` seconds.
    * ``raise_for_status()`` turns HTTP errors into exceptions.
    * Connection errors, timeouts and the statuses in :data:`RETRYABLE_STATUSES`
      are retried with exponential backoff, up to ``policy.max_attempts`` attempts.
    * Other 4xx errors (bad input) are not retried; they fail at once.

    Args:
        url: Endpoint URL.
        params: Query parameters (encoded by ``requests``).
        headers: Extra headers; a default ``User-Agent`` is added if absent.
        timeout: Seconds to wait for connect/read on each attempt.
        policy: Retry policy.
        session: Optional ``requests.Session`` (useful for connection reuse and tests).
        sleep: Function used to wait between attempts (replaceable in tests).

    Returns:
        The parsed JSON (usually a ``dict``).

    Raises:
        WeatherAPIError: on a non-retryable error or after the last failed attempt.
    """
    http = session or requests.Session()
    merged_headers = {"User-Agent": DEFAULT_USER_AGENT, **(headers or {})}
    last_error: Exception | None = None
    last_status: int | None = None
    last_reason: str | None = None

    for attempt in range(1, policy.max_attempts + 1):
        try:
            response = http.get(url, params=params, headers=merged_headers, timeout=timeout)
            last_status = response.status_code
            if response.status_code in RETRYABLE_STATUSES:
                last_reason = _server_reason(response)
                response.raise_for_status()
            try:
                response.raise_for_status()
            except requests.HTTPError as exc:  # non-retryable client error
                raise WeatherAPIError(
                    "Request rejected",
                    url=url,
                    attempts=attempt,
                    status=response.status_code,
                    reason=_server_reason(response),
                ) from exc
            try:
                return response.json()
            except ValueError as exc:
                raise WeatherAPIError(
                    "Response is not valid JSON", url=url, attempts=attempt, status=response.status_code
                ) from exc
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as exc:
            last_error = exc
            log.warning("Attempt %d/%d for %s failed: %s", attempt, policy.max_attempts, url, _short(exc))
            if attempt < policy.max_attempts:
                sleep(policy.delay(attempt))

    raise WeatherAPIError(
        f"Giving up after {policy.max_attempts} attempts: {type(last_error).__name__}",
        url=url,
        attempts=policy.max_attempts,
        status=last_status if isinstance(last_error, requests.HTTPError) else None,
        reason=last_reason or _short(last_error),
    ) from last_error
