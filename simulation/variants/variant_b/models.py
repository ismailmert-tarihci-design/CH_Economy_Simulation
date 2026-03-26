"""Variant B data models — Hero Card System.

All models are Pydantic BaseModels so every field is editable from the frontend.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class HeroCardRarity(str, Enum):
    """Rarity tiers within a hero's card deck. Names are display-only."""
    COMMON = "COMMON"
    UNCOMMON = "UNCOMMON"
    RARE = "RARE"
    EPIC = "EPIC"
    LEGENDARY = "LEGENDARY"


class PremiumPackRarity(str, Enum):
    """The 5 rarity tiers of hero premium packs."""
    BRONZE = "BRONZE"
    SILVER = "SILVER"
    GOLD = "GOLD"
    PLATINUM = "PLATINUM"
    DIAMOND = "DIAMOND"


# ---------------------------------------------------------------------------
# Hero card definitions (config, not runtime)
# ---------------------------------------------------------------------------

class HeroCardDef(BaseModel):
    """Definition of a single hero-specific card in the deck."""
    card_id: str
    hero_id: str
    rarity: HeroCardRarity
    name: str
    base_xp_on_upgrade: int = Field(default=10, description="Hero XP granted per upgrade of this card")


class SkillTreeNode(BaseModel):
    """One node in a hero's linear skill tree."""
    node_index: int
    hero_level_required: int
    cards_unlocked: List[str] = Field(default_factory=list, description="card_ids unlocked at this node")
    perk_label: str = Field(default="", description="Display label for perk/stat unlock (tracked as marker only)")


class HeroDef(BaseModel):
    """Complete definition of a hero and their card system."""
    hero_id: str
    name: str
    card_pool: List[HeroCardDef] = Field(default_factory=list, description="All cards in this hero's deck (~45)")
    skill_tree: List[SkillTreeNode] = Field(default_factory=list, description="Linear skill tree nodes")
    xp_per_level: List[int] = Field(default_factory=list, description="XP threshold to reach each level (index=level-1)")
    max_level: int = Field(default=50)
    starter_card_ids: List[str] = Field(default_factory=list, description="Cards available at hero unlock")


# ---------------------------------------------------------------------------
# Premium pack definitions (config)
# ---------------------------------------------------------------------------

class PremiumPackCardRate(BaseModel):
    """Drop rate for a specific card within a premium pack."""
    card_id: str
    drop_rate: float = Field(description="Probability weight for this card")


class PremiumPackDef(BaseModel):
    """Definition of a hero-specific premium card pack."""
    pack_id: str
    name: str
    pack_rarity: PremiumPackRarity
    featured_hero_ids: List[str] = Field(description="Hero(es) whose cards are in this pack")
    card_drop_rates: List[PremiumPackCardRate] = Field(
        default_factory=list,
        description="Per-card drop rates (displayed to player)"
    )
    cards_per_pack: int = Field(default=5)
    diamond_cost: int = Field(default=500, description="Price in diamonds")
    joker_rate: float = Field(default=0.02, description="Chance of pulling a hero joker per draw")
    dupe_boost_multiplier: float = Field(default=1.0, description="Multiplier on duplicates (>1 for limited offers)")


class PremiumPackSchedule(BaseModel):
    """Rotating availability window for a premium pack."""
    pack_id: str
    available_from_day: int
    available_until_day: int


# ---------------------------------------------------------------------------
# Hero upgrade cost tables (config, per-rarity)
# ---------------------------------------------------------------------------

class HeroUpgradeCostTable(BaseModel):
    """Upgrade costs and rewards for a specific hero card rarity."""
    rarity: HeroCardRarity
    duplicate_costs: List[int] = Field(default_factory=list, description="Dupes needed per level")
    coin_costs: List[int] = Field(default_factory=list, description="Coins needed per level")
    bluestar_rewards: List[int] = Field(default_factory=list, description="Bluestars earned per level")
    xp_rewards: List[int] = Field(default_factory=list, description="Hero XP earned per level upgrade")


# ---------------------------------------------------------------------------
# Drop algorithm config (Variant B specific)
# ---------------------------------------------------------------------------

class HeroDropConfig(BaseModel):
    """Drop algorithm parameters for Variant B."""
    hero_vs_shared_base_rate: float = Field(default=0.60, description="Base probability of hero card vs shared card")
    card_selection_mode: str = Field(default="lowest_level", description="Card selection strategy: lowest_level, weighted_rarity, gacha_rates")
    pity_counter_threshold: int = Field(default=0, description="Guaranteed hero card after N shared-only pulls (0=disabled)")
    streak_decay_shared: float = Field(default=0.6)
    streak_decay_hero: float = Field(default=0.3)


# ---------------------------------------------------------------------------
# Main config (satisfies ConfigProtocol)
# ---------------------------------------------------------------------------

class HeroCardConfig(BaseModel):
    """Main simulation config for Variant B — Hero Card System."""
    # Protocol fields
    num_days: int = Field(default=100)
    initial_coins: int = Field(default=0)
    initial_bluestars: int = Field(default=0)

    # Hero definitions
    heroes: List[HeroDef] = Field(default_factory=list)
    hero_unlock_schedule: Dict[int, List[str]] = Field(
        default_factory=dict,
        description="Day -> list of hero_ids unlocked on that day"
    )

    # Shared card settings (Gold/Blue, same structure as Variant A)
    num_gold_cards: int = Field(default=9)
    num_blue_cards: int = Field(default=14)
    max_shared_level: int = Field(default=100)
    shared_base_shared_rate: float = Field(default=0.70)
    shared_base_unique_rate: float = Field(default=0.30)

    # Hero card upgrade costs (per rarity)
    hero_upgrade_tables: List[HeroUpgradeCostTable] = Field(default_factory=list)

    # Hero joker settings
    joker_drop_rate_in_regular_packs: float = Field(default=0.01, description="Joker chance per regular pack pull")

    # Drop algorithm
    drop_config: HeroDropConfig = Field(default_factory=HeroDropConfig)

    # Pack schedules
    daily_pack_schedule: List[Dict[str, float]] = Field(
        default_factory=list,
        description="Daily pack schedule (shared packs)"
    )

    # Premium packs
    premium_packs: List[PremiumPackDef] = Field(default_factory=list)
    premium_pack_schedule: List[PremiumPackSchedule] = Field(default_factory=list)
    premium_pack_purchase_schedule: List[Dict[str, int]] = Field(
        default_factory=list,
        description="Simulated player purchases: [{pack_id: count_bought}, ...] per day"
    )

    # Shared subsystems (reuse existing models from Variant A)
    pet_system_config: Optional[Any] = None
    gear_system_config: Optional[Any] = None


# ---------------------------------------------------------------------------
# Runtime state models
# ---------------------------------------------------------------------------

class HeroCardState(BaseModel):
    """Runtime state of a single hero card."""
    card_id: str
    hero_id: str
    rarity: HeroCardRarity
    level: int = Field(default=1)
    duplicates: int = Field(default=0)
    unlocked: bool = Field(default=False, description="Whether card is available (via skill tree)")


class HeroProgressState(BaseModel):
    """Runtime state of a single hero."""
    hero_id: str
    xp: int = Field(default=0)
    level: int = Field(default=1)
    skill_tree_progress: int = Field(default=0, description="Index of last unlocked node")
    cards: Dict[str, HeroCardState] = Field(default_factory=dict, description="card_id -> state")
    joker_count: int = Field(default=0, description="Hero joker wildcards available")


class HeroCardGameState(BaseModel):
    """Complete runtime game state for Variant B."""
    day: int = Field(default=0)
    heroes: Dict[str, HeroProgressState] = Field(default_factory=dict)
    shared_cards: List[Any] = Field(default_factory=list, description="Gold/Blue shared cards (Card objects)")
    coins: int = Field(default=0)
    total_bluestars: int = Field(default=0)
    pity_counter: int = Field(default=0, description="Pulls since last hero card")
    pet_state: Optional[Any] = None
    gear_state: Optional[Any] = None


# ---------------------------------------------------------------------------
# Simulation result models
# ---------------------------------------------------------------------------

@dataclass
class HeroCardDailySnapshot:
    """Daily snapshot for Variant B. Satisfies DailySnapshotProtocol + extra fields."""
    # Protocol fields
    day: int = 0
    total_bluestars: int = 0
    bluestars_earned_today: int = 0
    coins_balance: int = 0
    coins_earned_today: int = 0
    coins_spent_today: int = 0
    category_avg_levels: Dict[str, float] = field(default_factory=dict)
    pull_counts_by_type: Dict[str, int] = field(default_factory=dict)
    pack_counts_by_type: Dict[str, int] = field(default_factory=dict)

    # Variant B specific
    hero_xp_today: Dict[str, int] = field(default_factory=dict)
    hero_levels: Dict[str, int] = field(default_factory=dict)
    hero_card_avg_levels: Dict[str, float] = field(default_factory=dict)
    skill_nodes_unlocked_today: Dict[str, int] = field(default_factory=dict)
    cards_unlocked_today: int = 0
    jokers_received_today: int = 0
    jokers_used_today: int = 0
    premium_packs_opened: int = 0
    premium_diamonds_spent: int = 0

    # Shared subsystem events
    pet_events: List[Dict[str, Any]] = field(default_factory=list)
    gear_events: List[Dict[str, Any]] = field(default_factory=list)
    upgrades_today: List[Any] = field(default_factory=list)


class HeroSimResult(BaseModel):
    """Simulation result for Variant B. Satisfies SimResultProtocol."""
    daily_snapshots: List[Any] = Field(default_factory=list)
    total_bluestars: int = Field(default=0)
    total_coins_earned: int = Field(default=0)
    total_coins_spent: int = Field(default=0)
    total_upgrades: Dict[str, Any] = Field(default_factory=dict)
    pull_logs: List[Any] = Field(default_factory=list)
    # Variant B specific aggregates
    final_hero_levels: Dict[str, int] = Field(default_factory=dict)
    final_hero_xp: Dict[str, int] = Field(default_factory=dict)
    total_premium_diamonds_spent: int = Field(default=0)
    total_jokers_received: int = Field(default=0)
