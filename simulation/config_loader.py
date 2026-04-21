"""
Configuration loader for the Bluestar Economy Simulator.

Loads default configuration from JSON files in data/defaults/
and returns a SimConfig object.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from simulation.models import (
    SimConfig,
    PackConfig,
    UpgradeTable,
    DuplicateRange,
    CoinPerDuplicate,
    ProgressionMapping,
    UserProfile,
    CardCategory,
    PetTierConfig,
    PetLevelConfig,
    PetDuplicateConfig,
    PetBuildConfig,
    PetSystemConfig,
    HeroSystemConfig,
    GearSystemConfig,
    HeroUnlockTable,
    GearDesignIncomeRow,
    GearSlotCostRow,
    GearDesignConfig,
    GearSlotCostConfig,
    HeroPowerConfig,
    PetPowerConfig,
    GearPowerConfig,
)


class ConfigValidationError(Exception):
    """Custom exception for configuration validation errors."""

    pass


def _get_defaults_dir() -> Path:
    """Get the path to the defaults directory."""
    # Get the directory of the current file
    current_dir = Path(__file__).parent.parent
    defaults_dir = current_dir / "data" / "defaults"
    return defaults_dir


def default_pet_config() -> dict[str, Any]:
    return {
        "tier_table": load_pet_tier_table().model_dump(mode="json"),
        "level_table": load_pet_level_table().model_dump(mode="json"),
        "duplicate_table": load_pet_duplicate_table().model_dump(mode="json"),
        "build_table": load_pet_build_table().model_dump(mode="json"),
        "eggs_per_day": [{"day_start": 1, "day_end": 365, "eggs": 2}],
    }


def default_hero_config() -> dict[str, Any]:
    return {
        "unlock_rows": [
            {"day": 1, "hero_id": "hero_alpha", "unique_cards_added": 2},
            {"day": 7, "hero_id": "hero_beta", "unique_cards_added": 1},
            {"day": 14, "hero_id": "hero_gamma", "unique_cards_added": 1},
        ]
    }


def default_gear_config() -> dict[str, Any]:
    return {
        "design_income": load_gear_design_income().model_dump(mode="json"),
        "slot_costs": load_gear_slot_costs().model_dump(mode="json"),
    }


def _get_snapshot_path() -> Path:
    return _get_defaults_dir() / "variant_a_config.json"


def load_snapshot() -> "SimConfig | None":
    """Load a full SimConfig snapshot if one has been persisted, else None."""
    path = _get_snapshot_path()
    if not path.exists():
        return None
    try:
        return SimConfig.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_snapshot(config: "SimConfig") -> None:
    """Persist the full SimConfig as a single JSON snapshot (atomic overlay)."""
    path = _get_snapshot_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(config.model_dump_json(indent=2), encoding="utf-8")


def load_defaults() -> SimConfig:
    """
    Load default configuration.

    Prefers a full-config snapshot (variant_a_config.json) if present — this
    captures every edit made via the UI, including fields not covered by the
    per-file defaults (pet/hero/gear configs, num_days, initial amounts, etc.).
    Falls back to composing a SimConfig from the per-file defaults otherwise.

    Raises:
        FileNotFoundError: If any required JSON file is missing.
        ValueError: If JSON structure doesn't match expected schema.
        ConfigValidationError: If new system config sections are corrupt.
    """
    snapshot = load_snapshot()
    if snapshot is not None:
        return snapshot

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

    # Load daily pack schedule
    with open(defaults_dir / "daily_pack_schedule.json") as f:
        schedule_data = json.load(f)

    # Load pet system config (Task 5: backward compatibility)
    pet_system_config = None
    try:
        pet_config_path = defaults_dir / "pet_config.json"
        if pet_config_path.exists():
            with open(pet_config_path) as f:
                pet_data = json.load(f)
            pet_system_config = PetSystemConfig(**pet_data)
    except (ValueError, TypeError) as e:
        raise ConfigValidationError(
            f"Pet system config validation failed: {str(e)} - "
            "check pet_config.json format"
        )

    # Use default if file not found (legacy backward compatibility)
    if pet_system_config is None:
        pet_system_config = PetSystemConfig(**default_pet_config())

    # Load hero system config (Task 5: backward compatibility)
    hero_system_config = None
    try:
        hero_config_path = defaults_dir / "hero_config.json"
        if hero_config_path.exists():
            with open(hero_config_path) as f:
                hero_data = json.load(f)
            hero_system_config = HeroSystemConfig(**hero_data)
    except (ValueError, TypeError) as e:
        raise ConfigValidationError(
            f"Hero system config validation failed: {str(e)} - "
            "check hero_config.json format"
        )

    # Use default if file not found (legacy backward compatibility)
    if hero_system_config is None:
        hero_system_config = HeroSystemConfig(**default_hero_config())

    # Load gear system config (Task 5: backward compatibility)
    gear_system_config = None
    try:
        gear_config_path = defaults_dir / "gear_config.json"
        if gear_config_path.exists():
            with open(gear_config_path) as f:
                gear_data = json.load(f)
            gear_system_config = GearSystemConfig(**gear_data)
    except (ValueError, TypeError) as e:
        raise ConfigValidationError(
            f"Gear system config validation failed: {str(e)} - "
            "check gear_config.json format"
        )

    # Use default if file not found (legacy backward compatibility)
    if gear_system_config is None:
        gear_system_config = GearSystemConfig(**default_gear_config())

    # Create SimConfig
    config = SimConfig(
        packs=packs,
        upgrade_tables=upgrade_tables,
        duplicate_ranges=duplicate_ranges,
        coin_per_duplicate=coin_per_duplicate,
        progression_mapping=progression_mapping,
        unique_unlock_schedule=unique_unlock_schedule,
        daily_pack_schedule=schedule_data,
        num_days=100,
        pet_system_config=pet_system_config,
        hero_system_config=hero_system_config,
        gear_system_config=gear_system_config,
    )

    return config


def save_defaults(config: "SimConfig") -> None:
    """
    Save the current SimConfig as the new default configuration.

    Writes each config section back to its corresponding JSON file
    in data/defaults/. Creates timestamped backups before overwriting.

    Args:
        config: SimConfig object to persist as defaults.
    """
    import shutil
    from datetime import datetime

    defaults_dir = _get_defaults_dir()
    backup_dir = defaults_dir / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def _backup_and_write(filename: str, data: Any) -> None:
        path = defaults_dir / filename
        if path.exists():
            shutil.copy2(path, backup_dir / f"{path.stem}_{timestamp}{path.suffix}")
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    # Pack configs
    pack_data = {"packs": [p.model_dump() for p in config.packs]}
    _backup_and_write("pack_configs.json", pack_data)

    # Upgrade tables
    upgrade_data = {
        cat.value: table.model_dump() for cat, table in config.upgrade_tables.items()
    }
    _backup_and_write("upgrade_tables.json", upgrade_data)

    # Duplicate ranges
    dup_data = {
        cat.value: dr.model_dump() for cat, dr in config.duplicate_ranges.items()
    }
    _backup_and_write("duplicate_ranges.json", dup_data)

    # Coin per duplicate
    coin_data = {
        cat.value: cpd.model_dump() for cat, cpd in config.coin_per_duplicate.items()
    }
    _backup_and_write("coin_per_duplicate.json", coin_data)

    # Progression mapping
    shared_to_unique = {
        str(s): u
        for s, u in zip(
            config.progression_mapping.shared_levels,
            config.progression_mapping.unique_levels,
        )
    }
    _backup_and_write(
        "progression_mapping.json", {"shared_to_unique": shared_to_unique}
    )

    # Unique unlock schedule
    schedule_data = {str(k): v for k, v in config.unique_unlock_schedule.items()}
    _backup_and_write("unique_unlock_schedule.json", schedule_data)

    # Daily pack schedule
    _backup_and_write("daily_pack_schedule.json", config.daily_pack_schedule)


def _get_profiles_dir() -> Path:
    current_dir = Path(__file__).parent.parent
    return current_dir / "data" / "profiles"


def list_profiles() -> list[str]:
    profiles_dir = _get_profiles_dir()
    if not profiles_dir.exists():
        return []
    return sorted(p.stem for p in profiles_dir.glob("*.json"))


def load_profile(name: str) -> UserProfile:
    profiles_dir = _get_profiles_dir()
    path = profiles_dir / f"{name}.json"
    with open(path) as f:
        data = json.load(f)
    return UserProfile.model_validate(data)


def save_profile(profile: UserProfile) -> None:
    profiles_dir = _get_profiles_dir()
    profiles_dir.mkdir(parents=True, exist_ok=True)
    path = profiles_dir / f"{profile.name}.json"
    with open(path, "w") as f:
        f.write(profile.model_dump_json(indent=2))


def delete_profile(name: str) -> None:
    profiles_dir = _get_profiles_dir()
    path = profiles_dir / f"{name}.json"
    if path.exists():
        path.unlink()


def _get_results_dir() -> Path:
    current_dir = Path(__file__).parent.parent
    return current_dir / "data" / "results"


def list_saved_results() -> list[dict[str, Any]]:
    """List all saved results with their metadata."""
    results_dir = _get_results_dir()
    if not results_dir.exists():
        return []

    results = []
    for path in sorted(
        results_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
    ):
        try:
            with open(path) as f:
                data = json.load(f)
            results.append(
                {
                    "filename": path.stem,
                    "name": data.get("name", path.stem),
                    "timestamp": data.get("timestamp", ""),
                    "description": data.get("description", ""),
                    "sim_mode": data.get("sim_mode", "unknown"),
                    "num_days": data.get("num_days", 0),
                    "num_runs": data.get("num_runs", 1),
                }
            )
        except Exception:
            continue
    return results


def save_result(result_data: dict[str, Any]) -> str:
    """Save a simulation result. Returns the filename."""
    results_dir = _get_results_dir()
    results_dir.mkdir(parents=True, exist_ok=True)

    # Create filename from name + timestamp
    safe_name = "".join(
        c if c.isalnum() or c in "-_" else "_" for c in result_data["name"]
    )
    timestamp = result_data["timestamp"].replace(":", "-").replace("T", "_")
    filename = f"{safe_name}_{timestamp}.json"

    path = results_dir / filename
    with open(path, "w") as f:
        json.dump(result_data, f, indent=2)

    return filename


def load_result(filename: str) -> dict[str, Any]:
    """Load a saved simulation result."""
    results_dir = _get_results_dir()
    path = results_dir / f"{filename}.json"
    with open(path) as f:
        return json.load(f)


def delete_result(filename: str) -> None:
    """Delete a saved simulation result."""
    results_dir = _get_results_dir()
    path = results_dir / f"{filename}.json"
    if path.exists():
        path.unlink()


def load_pet_tier_table() -> PetTierConfig:
    """Load pet tier table from JSON (tiers 1-15)."""
    defaults_dir = _get_defaults_dir()
    try:
        with open(defaults_dir / "pet_tier_table.json") as f:
            data = json.load(f)
        config = PetTierConfig(**data)
        return config
    except FileNotFoundError:
        raise FileNotFoundError("pet_tier_table.json not found in data/defaults/")
    except (ValueError, TypeError) as e:
        raise ConfigValidationError(f"Pet tier table validation failed: {str(e)}")


def load_pet_level_table() -> PetLevelConfig:
    """Load pet level table from JSON (levels 1-100 × rarity)."""
    defaults_dir = _get_defaults_dir()
    try:
        with open(defaults_dir / "pet_level_table.json") as f:
            data = json.load(f)
        config = PetLevelConfig(**data)
        return config
    except FileNotFoundError:
        raise FileNotFoundError("pet_level_table.json not found in data/defaults/")
    except (ValueError, TypeError) as e:
        raise ConfigValidationError(f"Pet level table validation failed: {str(e)}")


def load_pet_duplicate_table() -> PetDuplicateConfig:
    """Load pet duplicate table from JSON (levels 1-100 × rarity)."""
    defaults_dir = _get_defaults_dir()
    try:
        with open(defaults_dir / "pet_duplicate_table.json") as f:
            data = json.load(f)
        config = PetDuplicateConfig(**data)
        return config
    except FileNotFoundError:
        raise FileNotFoundError("pet_duplicate_table.json not found in data/defaults/")
    except (ValueError, TypeError) as e:
        raise ConfigValidationError(f"Pet duplicate table validation failed: {str(e)}")


def load_pet_build_table() -> PetBuildConfig:
    """Load pet build cost table from JSON (builds 1-8)."""
    defaults_dir = _get_defaults_dir()
    try:
        with open(defaults_dir / "pet_build_table.json") as f:
            data = json.load(f)
        config = PetBuildConfig(**data)
        return config
    except FileNotFoundError:
        raise FileNotFoundError("pet_build_table.json not found in data/defaults/")
    except (ValueError, TypeError) as e:
        raise ConfigValidationError(f"Pet build table validation failed: {str(e)}")


def _validate_gear_day_ranges(rows: list[GearDesignIncomeRow]) -> None:
    sorted_rows = sorted(rows, key=lambda row: row.day_start)
    for idx, row in enumerate(sorted_rows):
        if row.day_start > row.day_end:
            raise ConfigValidationError(
                f"Invalid day range at index {idx}: day_start ({row.day_start}) "
                f"must be <= day_end ({row.day_end})"
            )
        if idx == 0:
            continue
        prev_row = sorted_rows[idx - 1]
        if prev_row.day_end >= row.day_start:
            raise ConfigValidationError(
                "Overlapping day ranges in gear design income table: "
                f"{prev_row.day_start}-{prev_row.day_end} overlaps with "
                f"{row.day_start}-{row.day_end}"
            )


def _validate_gear_slot_costs(rows: list[GearSlotCostRow]) -> None:
    required_pairs = {
        (slot_id, level) for slot_id in range(1, 7) for level in range(1, 101)
    }
    seen_pairs: set[tuple[int, int]] = set()

    for row in rows:
        pair = (row.slot_id, row.level)
        if pair in seen_pairs:
            raise ConfigValidationError(
                "Gear slot cost table has duplicate slot/level row: "
                f"slot_id={row.slot_id}, level={row.level}"
            )
        seen_pairs.add(pair)

    missing_pairs = sorted(required_pairs - seen_pairs)
    extra_pairs = sorted(seen_pairs - required_pairs)
    if missing_pairs or extra_pairs:
        details: list[str] = []
        if missing_pairs:
            details.append(
                f"missing {len(missing_pairs)} pair(s), first={missing_pairs[0]}"
            )
        if extra_pairs:
            details.append(
                f"unexpected {len(extra_pairs)} pair(s), first={extra_pairs[0]}"
            )
        raise ConfigValidationError(
            "Gear slot cost table incomplete: " + "; ".join(details)
        )


def load_gear_design_income() -> GearDesignConfig:
    defaults_dir = _get_defaults_dir()
    try:
        with open(defaults_dir / "gear_design_income_table.json") as f:
            data = json.load(f)
        config = GearDesignConfig(**data)
        _validate_gear_day_ranges(config.income_table)
        return config
    except FileNotFoundError:
        raise FileNotFoundError(
            "gear_design_income_table.json not found in data/defaults/"
        )
    except (ValueError, TypeError) as e:
        raise ConfigValidationError(
            f"Gear design income table validation failed: {str(e)}"
        )


def load_gear_slot_costs() -> GearSlotCostConfig:
    defaults_dir = _get_defaults_dir()
    try:
        with open(defaults_dir / "gear_slot_cost_table.json") as f:
            data = json.load(f)
        config = GearSlotCostConfig(**data)
        _validate_gear_slot_costs(config.cost_table)
        return config
    except FileNotFoundError:
        raise FileNotFoundError("gear_slot_cost_table.json not found in data/defaults/")
    except (ValueError, TypeError) as e:
        raise ConfigValidationError(f"Gear slot cost table validation failed: {str(e)}")


def load_hero_power_table() -> HeroPowerConfig:
    """Load hero power table from JSON (levels 1-50)."""
    defaults_dir = _get_defaults_dir()
    try:
        with open(defaults_dir / "hero_power_table.json") as f:
            data = json.load(f)
        return HeroPowerConfig(**data)
    except FileNotFoundError:
        raise FileNotFoundError("hero_power_table.json not found in data/defaults/")
    except (ValueError, TypeError) as e:
        raise ConfigValidationError(f"Hero power table validation failed: {str(e)}")


def load_pet_power_table() -> PetPowerConfig:
    """Load pet power table from JSON (levels 1-100 × rarity)."""
    defaults_dir = _get_defaults_dir()
    try:
        with open(defaults_dir / "pet_power_table.json") as f:
            data = json.load(f)
        return PetPowerConfig(**data)
    except FileNotFoundError:
        raise FileNotFoundError("pet_power_table.json not found in data/defaults/")
    except (ValueError, TypeError) as e:
        raise ConfigValidationError(f"Pet power table validation failed: {str(e)}")


def load_gear_power_table() -> GearPowerConfig:
    """Load gear power table from JSON (levels 1-100)."""
    defaults_dir = _get_defaults_dir()
    try:
        with open(defaults_dir / "gear_power_table.json") as f:
            data = json.load(f)
        return GearPowerConfig(**data)
    except FileNotFoundError:
        raise FileNotFoundError("gear_power_table.json not found in data/defaults/")
    except (ValueError, TypeError) as e:
        raise ConfigValidationError(f"Gear power table validation failed: {str(e)}")


def load_hero_unlocks(hero_unlock_rows: list[dict[str, Any]]) -> HeroUnlockTable:
    """
    Load and validate hero unlock table with deterministic same-day aggregation.

    Validates each row format (day, hero_id, unique_cards_added), rejects negative
    card counts, and aggregates multiple same-day heroes deterministically.

    Args:
        hero_unlock_rows: List of dicts with {day, hero_id, unique_cards_added}

    Returns:
        HeroUnlockTable: Aggregated unlock table with schedule and total cards.

    Raises:
        ConfigValidationError: If validation fails or negative card counts detected.
    """
    from simulation.models import HeroUnlockRow

    unlock_schedule: dict[int, dict[str, int]] = {}
    total_unique_cards = 0

    try:
        for i, row_data in enumerate(hero_unlock_rows):
            row = HeroUnlockRow(**row_data)
            day = row.day
            hero_id = row.hero_id
            cards = row.unique_cards_added

            if cards < 0:
                raise ConfigValidationError(
                    f"Row {i}: hero '{hero_id}' has negative unique_cards_added: {cards}"
                )

            if day not in unlock_schedule:
                unlock_schedule[day] = {}

            unlock_schedule[day][hero_id] = unlock_schedule[day].get(hero_id, 0) + cards
            total_unique_cards += cards

    except ConfigValidationError:
        raise
    except ValueError as e:
        raise ConfigValidationError(f"Hero unlock table validation failed: {str(e)}")
    except TypeError as e:
        raise ConfigValidationError(
            f"Hero unlock table type error: {str(e)} - expected row format: "
            "{day: int, hero_id: str, unique_cards_added: int}"
        )

    return HeroUnlockTable(
        unlock_schedule=unlock_schedule,
        total_unique_cards=total_unique_cards,
    )
