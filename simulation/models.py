"""
Data models for the Bluestar Economy Simulator.

Defines Pydantic v2 models for game state, configuration, and results.
All models support JSON serialization via model_dump_json() and model_validate_json().
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CardCategory(str, Enum):
    """Card category enum for the three card types."""

    GOLD_SHARED = "GOLD_SHARED"
    BLUE_SHARED = "BLUE_SHARED"
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
    """Reusable profile storing daily pack schedule and unique unlock schedule."""

    name: str
    daily_pack_schedule: List[Dict[str, float]]
    unique_unlock_schedule: Dict[int, int]


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
        default=0.70, description="Base rate for shared cards"
    )
    base_unique_rate: float = Field(
        default=0.30, description="Base rate for unique cards"
    )
    streak_decay_shared: float = Field(
        default=0.6, description="Streak decay rate for shared card drops"
    )
    streak_decay_unique: float = Field(
        default=0.3, description="Streak decay rate for unique card drops"
    )
    gap_base: float = Field(
        default=1.5, description="Exponential base for progression gap balancing"
    )
    gap_scale: float = Field(
        default=10.0,
        description="Multiplier applied to the gap before exponentiation (amplifies the nudge strength)",
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


class SimResult(BaseModel):
    """Results of a simulation run."""

    daily_snapshots: List[Any] = Field(default_factory=list)
    total_bluestars: int
    total_coins_earned: int
    total_coins_spent: int
    total_upgrades: Dict[str, Any] = Field(default_factory=dict)
    pull_logs: List[Any] = Field(default_factory=list)
