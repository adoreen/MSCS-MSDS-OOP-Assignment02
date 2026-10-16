"""Shared pytest configuration."""

from hypothesis import settings

# Deterministic property tests: same examples on every run (reproducibility requirement).
settings.register_profile("deterministic", derandomize=True, max_examples=300, deadline=None)
settings.load_profile("deterministic")
