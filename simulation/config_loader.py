"""
Configuration loader for the Bluestar Economy Simulator.

Loads default configuration from JSON files in data/defaults/
and returns a SimConfig object.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any

from simulation.models import (
    SimConfig,
    PackConfig,
    UpgradeTable,
    DuplicateRange,
    CoinPerDuplicate,
    ProgressionMapping,
    CardCategory,
)


def _get_defaults_dir() -> Path:
    """Get the path to the defaults directory."""
    # Get the directory of the current file
    current_dir = Path(__file__).parent.parent
    defaults_dir = current_dir / "data" / "defaults"
    return defaults_dir


def load_defaults() -> SimConfig:
    """
    Load default configuration from JSON files.

    Returns:
        SimConfig: Configuration object with all default values loaded.

    Raises:
        FileNotFoundError: If any required JSON file is missing.
        ValueError: If JSON structure doesn't match expected schema.
    """
    defaults_dir = _get_defaults_dir()

    # Load pack configs
    with open(defaults_dir / "pack_configs.json") as f:
        pack_data = json.load(f)
    packs = [PackConfig(**pack) for pack in pack_data["packs"]]

    # Load upgrade tables
    with open(defaults_dir / "upgrade_tables.json") as f:
        upgrade_data = json.load(f)
    upgrade_tables = {
        CardCategory(key): UpgradeTable(**value) for key, value in upgrade_data.items()
    }

    # Load duplicate ranges
    with open(defaults_dir / "duplicate_ranges.json") as f:
        duplicate_data = json.load(f)
    duplicate_ranges = {
        CardCategory(key): DuplicateRange(**value)
        for key, value in duplicate_data.items()
    }

    # Load coin per duplicate
    with open(defaults_dir / "coin_per_duplicate.json") as f:
        coin_data = json.load(f)
    coin_per_duplicate = {
        CardCategory(key): CoinPerDuplicate(**value) for key, value in coin_data.items()
    }

    # Load progression mapping
    with open(defaults_dir / "progression_mapping.json") as f:
        progression_data = json.load(f)
    # Convert the shared_to_unique dict to lists format expected by ProgressionMapping
    shared_to_unique = progression_data.get("shared_to_unique", {})
    shared_levels = sorted([int(k) for k in shared_to_unique.keys()])
    unique_levels = [shared_to_unique[str(k)] for k in shared_levels]
    progression_mapping = ProgressionMapping(
        shared_levels=shared_levels, unique_levels=unique_levels
    )

    # Load unique unlock schedule
    with open(defaults_dir / "unique_unlock_schedule.json") as f:
        schedule_data = json.load(f)
    # Convert string keys to integers
    unique_unlock_schedule = {int(k): v for k, v in schedule_data.items()}

    # Load pack averages
    with open(defaults_dir / "pack_averages.json") as f:
        averages_data = json.load(f)

    # Create SimConfig
    config = SimConfig(
        packs=packs,
        upgrade_tables=upgrade_tables,
        duplicate_ranges=duplicate_ranges,
        coin_per_duplicate=coin_per_duplicate,
        progression_mapping=progression_mapping,
        unique_unlock_schedule=unique_unlock_schedule,
        pack_averages=averages_data,
        num_days=100,  # Default simulation duration
    )

    return config
