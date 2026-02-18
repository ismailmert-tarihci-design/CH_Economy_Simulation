"""
Shared fixtures for all tests.

Provides reusable configurations and utilities for test cases.
"""

import pytest
from random import Random

from simulation.config_loader import load_defaults
from simulation.models import SimConfig, CardCategory, DuplicateRange


@pytest.fixture
def default_config() -> SimConfig:
    """Load default configuration for tests."""
    return load_defaults()


@pytest.fixture
def simple_config() -> SimConfig:
    """Minimal config for fast tests with boosted progression."""
    config = load_defaults()
    config.num_days = 10

    for pack_name in config.pack_averages.keys():
        config.pack_averages[pack_name] = 3.0

    for category in [CardCategory.GOLD_SHARED, CardCategory.BLUE_SHARED]:
        max_level = config.max_shared_level
        config.duplicate_ranges[category] = DuplicateRange(
            category=category,
            min_pct=[0.8] * max_level,
            max_pct=[1.2] * max_level,
        )

    max_unique = config.max_unique_level
    config.duplicate_ranges[CardCategory.UNIQUE] = DuplicateRange(
        category=CardCategory.UNIQUE,
        min_pct=[0.8] * max_unique,
        max_pct=[1.2] * max_unique,
    )

    return config


@pytest.fixture
def seeded_rng() -> Random:
    """Reproducible random number generator for MC tests."""
    return Random(42)
