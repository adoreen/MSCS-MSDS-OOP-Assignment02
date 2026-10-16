"""Contact details and the User-Agent sent with every request.

The brief requires our own university email in the User-Agent, and forbids
hardcoding contact details. The address therefore comes from the notebook's
configuration cell or the ``CONTACT_EMAIL`` environment variable.
"""

from __future__ import annotations

import os
import re

from .exceptions import ConfigurationError

APP_NAME = "advent2026-weather-coursework/1.0"
PLACEHOLDER_EMAIL = "your.name@university.example"
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def contact_email(configured: str | None = None) -> str:
    """Return the contact email from the config cell or the ``CONTACT_EMAIL`` variable.

    Raises:
        ConfigurationError: if no valid, non-placeholder address is set.
    """
    email = (configured or os.environ.get("CONTACT_EMAIL", "")).strip()
    if not email or email == PLACEHOLDER_EMAIL:
        raise ConfigurationError(
            "Set CONTACT_EMAIL (environment variable) or the config cell to your university email"
        )
    if not _EMAIL.match(email):
        raise ConfigurationError(f"Not a valid email address: {email!r}")
    return email


def user_agent(email: str | None) -> str:
    """Identifying User-Agent, e.g. ``"advent2026-weather-coursework/1.0 (you@uni.ac.ug)"``.

    ``None`` gives the bare application name (used only when no email is configured).
    """
    return f"{APP_NAME} ({email})" if email else APP_NAME
