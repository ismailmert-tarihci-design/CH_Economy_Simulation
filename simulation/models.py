"""
Data models for the Bluestar Economy Simulator.

Defines Pydantic v2 models for game state, configuration, and results.
All models support JSON serialization via model_dump_json() and model_validate_json().
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class CardCategory(str, Enum):
    """Card category enum for shared and unique card types."""

    GOLD_SHARED = "GOLD_SHARED"
    BLUE_SHARED = "BLUE_SHARED"
    GRAY_SHARED = "GRAY_SHARED"
    UNIQUE = "UNIQUE"


class Card(BaseModel):
    """Represents a single card in the player's collection."""

    id: str
    name: str
    category: CardCategory
    level: int = Field(default=1, description="Card level, defaults to 1")
    duplicates: int = Field(
        default=0, description="Number of duplicate copies, defaults to 0"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "card_1",
                "name": "Gold Shared Card",
                "category": "GOLD_SHARED",
            }
        }
    }


class StreakState(BaseModel):
    """Tracks streak information for the player."""

    streak_shared: int
    streak_unique: int
    streak_per_color: Dict[str, int] = Field(default_factory=dict)
    streak_per_hero: Dict[str, int] = Field(default_factory=dict)


class GameState(BaseModel):
    """Represents the complete game state at a given point in time."""

    day: int
    cards: List[Card] = Field(default_factory=list)
    coins: int
    total_bluestars: int
    streak_state: StreakState
    unlock_schedule: Dict[str, Any] = Field(default_factory=dict)
    daily_log: List[Any] = Field(default_factory=list)
    pet_state: Optional["PetState"] = Field(default=None)
    hero_state: Optional["HeroState"] = Field(default=None)
    gear_state: Optional["GearState"] = Field(default=None)


class CardTypesRange(BaseModel):
    """Min/max range for card types yielded at a given unlock threshold."""

    min: int
    max: int


class PackConfig(BaseModel):
    """Configuration for a card pack."""

    name: str
    card_types_table: Dict[int, CardTypesRange]


class UpgradeTable(BaseModel):
    """Upgrade cost and reward table for a specific card category."""

    category: CardCategory
    duplicate_costs: List[int]
    coin_costs: List[int]
    bluestar_rewards: List[int]


class DuplicateRange(BaseModel):
    """Defines the range of duplicate percentages for a category."""

    category: CardCategory
    min_pct: List[float]
    max_pct: List[float]


class CoinPerDuplicate(BaseModel):
    """Defines coin rewards per duplicate for a category."""

    category: CardCategory
    coins_per_dupe: List[int]


class ProgressionMapping(BaseModel):
    """Maps progression levels for shared and unique cards."""

    shared_levels: List[int]
    unique_levels: List[int]


class UserProfile(BaseModel):
    """Reusable profile storing simulation configuration.

    New profiles store the full SimConfig. Legacy profiles (pre-v2) only
    have daily_pack_schedule and unique_unlock_schedule and are loaded
    with backward compatibility.
    """

    name: str
    daily_pack_schedule: List[Dict[str, float]] = Field(default_factory=list)
    unique_unlock_schedule: Dict[int, int] = Field(default_factory=dict)
    full_config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Full SimConfig snapshot (JSON-serializable dict). "
        "None for legacy profiles that only stored schedules.",
    )


class PetState(BaseModel):
    """Tracks pet system state for the player."""

    tier: int = Field(default=1, description="Pet tier progression (1-15)")
    summon_count: int = Field(default=0, description="Total pet summons performed")
    owned_pets: Dict[str, bool] = Field(
        default_factory=dict,
        description="Pet ID -> owned status (config-driven pet IDs)",
    )
    pet_levels: Dict[str, int] = Field(
        default_factory=dict,
        description="Pet ID -> level (1-100), config-driven pets",
    )
    pet_duplicates: Dict[str, int] = Field(
        default_factory=dict,
        description="Pet ID -> duplicate count, config-driven pets",
    )
    build_levels: Dict[str, int] = Field(
        default_factory=dict,
        description="Pet ID -> build level (1-8), config-driven pets",
    )


class HeroState(BaseModel):
    """Tracks hero system state for the player."""

    unlocked_heroes: List[str] = Field(
        default_factory=list,
        description="List of unlocked hero IDs (config-driven hero pool)",
    )
    unique_card_count: int = Field(
        default=0,
        description="Day-based increment count for unique card pool tracking",
    )


class GearState(BaseModel):
    """Tracks gear system state for the player."""

    slot_levels: Dict[int, int] = Field(
        default_factory=dict,
        description="Slot index (0-5) -> level (1-100)",
    )
    design_budgets: Dict[int, int] = Field(
        default_factory=dict,
        description="Slot index (0-5) -> design budget remaining",
    )


class PetSystemConfig(BaseModel):
    """Configuration placeholder for pet system tables (table-driven design)."""

    tier_table: Optional["PetTierConfig"] = Field(default=None)
    level_table: Optional["PetLevelConfig"] = Field(default=None)
    duplicate_table: Optional["PetDuplicateConfig"] = Field(default=None)
    build_table: Optional["PetBuildConfig"] = Field(default=None)
    eggs_per_day: Optional[List[Dict[str, int]]] = Field(default=None)


class HeroSystemConfig(BaseModel):
    """Configuration placeholder for hero system tables (table-driven design)."""

    unlock_rows: Optional[List["HeroUnlockRow"]] = Field(default=None)


class GearSystemConfig(BaseModel):
    """Configuration placeholder for gear system tables (table-driven design)."""

    design_income: Optional["GearDesignConfig"] = Field(default=None)
    slot_costs: Optional["GearSlotCostConfig"] = Field(default=None)


class SimConfig(BaseModel):
    """Main simulation configuration."""

    packs: List[PackConfig]
    upgrade_tables: Dict[CardCategory, UpgradeTable]
    duplicate_ranges: Dict[CardCategory, DuplicateRange]
    coin_per_duplicate: Dict[CardCategory, CoinPerDuplicate]
    progression_mapping: ProgressionMapping
    unique_unlock_schedule: Dict[int, int]
    daily_pack_schedule: List[Dict[str, float]]
    num_days: int
    initial_coins: int = Field(default=0)
    initial_bluestars: int = Field(default=0)
    mc_runs: Optional[int] = None
    base_shared_rate: float = Field(
        default=0.70,
        description="Normal drop rate of Shared Cards (Revamp Master Doc: 70%)",
    )
    base_unique_rate: float = Field(
        default=0.30,
        description="Normal drop rate of Unique Cards (Revamp Master Doc: 30%)",
    )
    streak_decay_shared: float = Field(
        default=0.6, description="Streak decay rate for shared card drops"
    )
    streak_decay_unique: float = Field(
        default=0.3, description="Streak decay rate for unique card drops"
    )
    gap_base: float = Field(
        default=1.5,
        description="Exponential base for gap adjustment. "
        "WShared = BaseShared * gap_base^Gap, WUnique = BaseUnique * gap_base^(-Gap). "
        "Higher values make the algorithm react more aggressively to progression imbalance.",
    )
    unique_candidate_pool: int = Field(
        default=10,
        description="Top-N lowest-level unique cards considered for selection",
    )
    num_gold_cards: int = Field(
        default=9, description="Number of Gold Shared cards in the collection"
    )
    num_blue_cards: int = Field(
        default=14, description="Number of Blue Shared cards in the collection"
    )
    max_shared_level: int = Field(
        default=100, description="Maximum level for shared cards"
    )
    max_unique_level: int = Field(
        default=10, description="Maximum level for unique cards"
    )
    pet_system_config: Optional["PetSystemConfig"] = Field(
        default=None,
        description="Pet system configuration (table-driven design)",
    )
    hero_system_config: Optional["HeroSystemConfig"] = Field(
        default=None,
        description="Hero system configuration (table-driven design)",
    )
    gear_system_config: Optional["GearSystemConfig"] = Field(
        default=None,
        description="Gear system configuration (table-driven design)",
    )


class SimResult(BaseModel):
    """Results of a simulation run."""

    daily_snapshots: List[Any] = Field(default_factory=list)
    total_bluestars: int
    total_coins_earned: int
    total_coins_spent: int
    total_upgrades: Dict[str, Any] = Field(default_factory=dict)
    pull_logs: List[Any] = Field(default_factory=list)


class SavedResult(BaseModel):
    """A saved simulation result with its configuration and metadata."""

    name: str = Field(description="User-provided name for this saved result")
    timestamp: str = Field(description="ISO format timestamp when saved")
    description: str = Field(default="", description="Optional description")
    sim_mode: str = Field(description="'deterministic' or 'monte_carlo'")
    result: Dict[str, Any] = Field(description="Serialized SimResult or MCResult")
    config: Dict[str, Any] = Field(description="Serialized SimConfig used for this run")
    num_days: int = Field(description="Number of days simulated")
    num_runs: int = Field(
        default=1, description="Number of MC runs (1 for deterministic)"
    )


class HeroUnlockRow(BaseModel):
    """Single row in hero unlock table."""

    day: int = Field(
        gt=0,
        description="Day when hero unlocks (must be positive integer)",
    )
    hero_id: str = Field(
        min_length=1,
        description="Unique hero identifier (non-empty string)",
    )
    unique_cards_added: int = Field(
        ge=0,
        description="Number of unique cards added to pool on this day (non-negative)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "day": 1,
                "hero_id": "hero_001",
                "unique_cards_added": 5,
            }
        }
    }


class HeroUnlockTable(BaseModel):
    """Aggregated hero unlock table with deterministic handling of same-day entries."""

    unlock_schedule: Dict[int, Dict[str, int]] = Field(
        default_factory=dict,
        description="day -> {hero_id -> unique_cards_added} mapping",
    )
    total_unique_cards: int = Field(
        default=0,
        description="Total unique cards added across all unlocks",
    )


class GearDesignIncomeRow(BaseModel):
    """Design income per day-range."""

    day_start: int = Field(ge=1, description="Start day (inclusive)")
    day_end: int = Field(ge=1, description="End day (inclusive)")
    designs_per_day: int = Field(
        ge=0, description="Designs earned per day in this range"
    )


class GearSlotCostRow(BaseModel):
    """Design cost per slot level upgrade."""

    slot_id: int = Field(ge=1, le=6, description="Slot ID (1-6)")
    level: int = Field(ge=1, le=100, description="Level (1-100)")
    design_cost: int = Field(
        ge=0, description="Designs required to upgrade to this level"
    )


class GearDesignConfig(BaseModel):
    """Configuration for gear design income."""

    income_table: List[GearDesignIncomeRow] = Field(
        description="Day-range to designs-per-day mapping"
    )


class GearSlotCostConfig(BaseModel):
    """Configuration for gear slot upgrade design costs."""

    cost_table: List[GearSlotCostRow] = Field(
        description="Slot × level to design cost mapping"
    )


# Placeholder models for Pet system (implemented in earlier tasks)
class PetTierRow(BaseModel):
    """Placeholder: Single row in pet tier table."""

    tier: int
    summons_to_lvl_up: int
    rarity_probabilities: Dict[str, float]

    @model_validator(mode="after")
    def _validate_probabilities(self):
        total = sum(self.rarity_probabilities.values())
        if abs(total - 100.0) > 0.01:
            raise ValueError(
                f"Pet tier {self.tier} rarity probabilities must sum to 100, got {total}"
            )
        if any(value < 0 for value in self.rarity_probabilities.values()):
            raise ValueError("Pet rarity probabilities must be non-negative")
        return self


class PetTierConfig(BaseModel):
    """Placeholder: Pet tier table configuration."""

    tiers: List[PetTierRow]

    @model_validator(mode="after")
    def _validate_tier_range(self):
        tiers = sorted(row.tier for row in self.tiers)
        if tiers != list(range(1, 16)):
            raise ValueError("Pet tier table must contain each tier 1..15 exactly once")
        return self


class PetLevelRow(BaseModel):
    """Placeholder: Single row in pet level table."""

    rarity: str
    level: int
    resource_required: int


class PetLevelConfig(BaseModel):
    """Placeholder: Pet level table configuration."""

    levels: List[PetLevelRow]

    @model_validator(mode="after")
    def _validate_level_coverage(self):
        rarity_to_levels: Dict[str, set[int]] = {}
        for row in self.levels:
            rarity_to_levels.setdefault(row.rarity, set()).add(row.level)
            if row.resource_required < 0:
                raise ValueError("Pet level resource_required must be non-negative")
        for rarity, levels in rarity_to_levels.items():
            if levels != set(range(1, 101)):
                raise ValueError(
                    f"Pet level table for rarity '{rarity}' must contain levels 1..100"
                )
        return self


class PetDuplicateRow(BaseModel):
    """Placeholder: Single row in pet duplicate table."""

    rarity: str
    level: int
    duplicates_required: int


class PetDuplicateConfig(BaseModel):
    """Placeholder: Pet duplicate table configuration."""

    duplicates: List[PetDuplicateRow]

    @model_validator(mode="after")
    def _validate_duplicate_coverage(self):
        rarity_to_levels: Dict[str, set[int]] = {}
        for row in self.duplicates:
            rarity_to_levels.setdefault(row.rarity, set()).add(row.level)
            if row.duplicates_required < 0:
                raise ValueError("Pet duplicate requirement must be non-negative")
        for rarity, levels in rarity_to_levels.items():
            if levels != set(range(1, 101)):
                raise ValueError(
                    f"Pet duplicate table for rarity '{rarity}' must contain levels 1..100"
                )
        return self


class PetBuildRow(BaseModel):
    """Placeholder: Single row in pet build table."""

    build_level: int
    spirit_stones_cost: int


class PetBuildConfig(BaseModel):
    """Placeholder: Pet build configuration."""

    builds: List[PetBuildRow]

    @model_validator(mode="after")
    def _validate_build_coverage(self):
        build_levels = sorted(row.build_level for row in self.builds)
        if build_levels != list(range(1, 9)):
            raise ValueError(
                "Pet build table must contain build levels 1..8 exactly once"
            )
        if any(row.spirit_stones_cost < 0 for row in self.builds):
            raise ValueError("Pet build spirit_stones_cost must be non-negative")
        return self


# ── Power Tables ──────────────────────────────────────────────────────


class HeroPowerRow(BaseModel):
    """Single row mapping hero level to power."""

    level: int = Field(ge=1, le=50, description="Hero level (1-50)")
    power: int = Field(ge=0, description="Power granted at this hero level")


class HeroPowerConfig(BaseModel):
    """Hero level → power lookup table."""

    levels: List[HeroPowerRow]

    @model_validator(mode="after")
    def _validate_level_coverage(self):
        seen = sorted(row.level for row in self.levels)
        if seen != list(range(1, 51)):
            raise ValueError(
                "Hero power table must contain each level 1..50 exactly once"
            )
        return self


class PetPowerRow(BaseModel):
    """Single row mapping (rarity, pet level) to power."""

    rarity: str
    level: int = Field(ge=1, le=100, description="Pet level (1-100)")
    power: int = Field(ge=0, description="Power granted at this rarity/level")


class PetPowerConfig(BaseModel):
    """Pet (rarity × level) → power lookup table."""

    levels: List[PetPowerRow]

    @model_validator(mode="after")
    def _validate_level_coverage(self):
        rarity_to_levels: Dict[str, set[int]] = {}
        for row in self.levels:
            rarity_to_levels.setdefault(row.rarity, set()).add(row.level)
        for rarity, levels in rarity_to_levels.items():
            if levels != set(range(1, 101)):
                raise ValueError(
                    f"Pet power table for rarity '{rarity}' must contain levels 1..100"
                )
        return self


class GearPowerRow(BaseModel):
    """Single row mapping gear level to power."""

    level: int = Field(ge=1, le=100, description="Gear level (1-100)")
    power: int = Field(ge=0, description="Power granted at this gear level")


class GearPowerConfig(BaseModel):
    """Gear level → power lookup table."""

    levels: List[GearPowerRow]

    @model_validator(mode="after")
    def _validate_level_coverage(self):
        seen = sorted(row.level for row in self.levels)
        if seen != list(range(1, 101)):
            raise ValueError(
                "Gear power table must contain each level 1..100 exactly once"
            )
        return self
