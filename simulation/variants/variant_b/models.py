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
    """Rarity tiers within a hero's card deck."""
    GRAY = "GRAY"
    BLUE = "BLUE"
    GOLD = "GOLD"


# ---------------------------------------------------------------------------
# Shared card models (Gold/Blue/Gray — separate from hero cards)
# ---------------------------------------------------------------------------

class SharedUpgradeCostTable(BaseModel):
    """Upgrade costs and rewards for a shared card category (no XP)."""
    category: str = Field(description="GOLD_SHARED / BLUE_SHARED / GRAY_SHARED")
    duplicate_costs: List[int] = Field(default_factory=list)
    coin_costs: List[int] = Field(default_factory=list)
    bluestar_rewards: List[int] = Field(default_factory=list)


class SharedDuplicateRange(BaseModel):
    """Per-category duplicate percentage ranges for shared card pulls."""
    category: str = Field(description="GOLD_SHARED / BLUE_SHARED / GRAY_SHARED")
    min_pct: List[float] = Field(default_factory=list)
    max_pct: List[float] = Field(default_factory=list)
    coins_per_dupe: List[int] = Field(default_factory=list)




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


class HeroCardTypesRange(BaseModel):
    """Min/max range for card types yielded at a given unlock threshold."""
    min: int
    max: int


class HeroPackType(BaseModel):
    """Pack type definition with progression-scaled card yields."""
    name: str
    card_types_table: Dict[int, HeroCardTypesRange] = Field(
        description="Maps total unlocked card count → min/max card types per pack opening"
    )


class PremiumPackAdditionalReward(BaseModel):
    """An additional reward that can drop from a premium pack."""
    reward_type: str = Field(description="Type of reward (e.g. 'coins', 'bluestars', 'hero_tokens')")
    amount: int = Field(default=1, description="Amount of reward")
    probability: float = Field(default=0.10, description="Chance of this reward dropping per pack")


class PremiumPackPullRarity(BaseModel):
    """Rarity weights for a specific pull position in a premium pack."""
    gray_weight: float = Field(default=0.64)
    blue_weight: float = Field(default=0.30)
    gold_weight: float = Field(default=0.06)


class PremiumPackDef(BaseModel):
    """Definition of a hero-specific premium card pack (single tier per hero)."""
    pack_id: str
    name: str
    featured_hero_ids: List[str] = Field(description="Hero(es) whose cards are in this pack")
    card_drop_rates: List[PremiumPackCardRate] = Field(
        default_factory=list,
        description="Legacy per-card drop rates (ignored when pull_rarity_schedule is set)"
    )
    min_cards_per_pack: int = Field(default=4, description="Minimum cards drawn per pack")
    max_cards_per_pack: int = Field(default=8, description="Maximum cards drawn per pack")
    diamond_cost: int = Field(default=500, description="Price in diamonds")
    joker_rate: float = Field(default=0.02, description="Chance of pulling a hero joker per draw")
    gold_guarantee: bool = Field(default=True, description="Guarantee at least one GOLD rarity card per pack")
    hero_tokens_per_pack: int = Field(default=5, description="Hero Tokens gifted per pack opening")
    additional_rewards: List[PremiumPackAdditionalReward] = Field(
        default_factory=list,
        description="Probability-based additional rewards per pack"
    )
    # Per-pull rarity schedule (index = pull position, up to 4)
    pull_rarity_schedule: List[PremiumPackPullRarity] = Field(
        default_factory=list,
        description="Rarity weights per pull position. After gold is pulled, uses default_rarity_weights."
    )
    default_rarity_weights: PremiumPackPullRarity = Field(
        default_factory=PremiumPackPullRarity,
        description="Fallback rarity weights after gold has been pulled"
    )
    # Dupe override: rarity name -> % of required dupes for next level (0 = use normal formula)
    dupe_pct_per_rarity: Dict[str, float] = Field(
        default_factory=dict,
        description="Rarity -> % of dupe cost for next level (e.g. 0.5 = 50%). Keys: GRAY, BLUE, GOLD. Empty = use normal formula."
    )


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


class HeroDuplicateRange(BaseModel):
    """Per-rarity duplicate percentage ranges for hero card pulls.

    When a hero card is pulled, dupes received = round(dupe_cost_for_next_level * random(min_pct, max_pct)).
    Each index corresponds to card level (index 0 = level 1).
    """
    rarity: HeroCardRarity
    min_pct: List[float] = Field(default_factory=list, description="Min % of next-level dupe cost received per pull")
    max_pct: List[float] = Field(default_factory=list, description="Max % of next-level dupe cost received per pull")
    coins_per_dupe: List[int] = Field(default_factory=list, description="Coins earned per duplicate at each card level")


# ---------------------------------------------------------------------------
# Drop algorithm config (Variant B specific)
# ---------------------------------------------------------------------------

class HeroDropConfig(BaseModel):
    """Drop algorithm parameters for Variant B."""
    hero_vs_shared_base_rate: float = Field(default=0.50, description="Base probability of hero card vs shared card")
    pity_counter_threshold: int = Field(default=0, description="Guaranteed hero card after N shared-only pulls (0=disabled)")

    # Hero bucket selection weights (heroes ranked by level, divided into 3 tiers)
    bucket_bottom_weight: float = Field(default=0.40, description="Probability of selecting from lowest-level hero bucket")
    bucket_middle_weight: float = Field(default=0.35, description="Probability of selecting from mid-level hero bucket")
    bucket_top_weight: float = Field(default=0.25, description="Probability of selecting from highest-level hero bucket")

    # Rarity roll weights for hero card drops
    rarity_weight_gray: float = Field(default=0.64, description="Probability of dropping a GRAY card")
    rarity_weight_blue: float = Field(default=0.30, description="Probability of dropping a BLUE card")
    rarity_weight_gold: float = Field(default=0.06, description="Probability of dropping a GOLD card")

    # Anti-streak decay
    streak_decay_shared: float = Field(default=0.6, description="Weight decay for repeated shared pulls")
    streak_decay_hero: float = Field(default=0.3, description="Weight multiplier per consecutive pull of the same hero")


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

    # Shared card settings (Gold/Blue/Gray)
    num_gold_cards: int = Field(default=9)
    num_blue_cards: int = Field(default=14)
    num_gray_cards: int = Field(default=20)
    max_shared_level: int = Field(default=100)
    shared_base_shared_rate: float = Field(default=0.70)
    shared_base_unique_rate: float = Field(default=0.30)

    # Hero card upgrade costs (per rarity)
    hero_upgrade_tables: List[HeroUpgradeCostTable] = Field(default_factory=list)

    # Shared card upgrade costs and duplicate ranges (per category)
    shared_upgrade_tables: List[SharedUpgradeCostTable] = Field(default_factory=list)
    shared_duplicate_ranges: List[SharedDuplicateRange] = Field(default_factory=list)

    # Shared hero XP (one level across all heroes)
    shared_xp_per_level: List[int] = Field(default_factory=list, description="XP threshold per shared hero level")
    shared_max_hero_level: int = Field(default=50)

    # Hero joker settings
    joker_drop_rate_in_regular_packs: float = Field(default=0.01, description="Joker chance per regular pack pull")

    # Drop algorithm
    drop_config: HeroDropConfig = Field(default_factory=HeroDropConfig)

    # Pack types and daily schedule
    pack_types: List[HeroPackType] = Field(
        default_factory=list,
        description="Pack type definitions with progression-scaled card yields"
    )
    daily_pack_schedule: List[Dict[str, float]] = Field(
        default_factory=list,
        description="Daily pack schedule: [{pack_name: expected_count}, ...] per day cycle"
    )

    # Duplicate ranges (per rarity, % of next-level dupe cost per pull)
    hero_duplicate_ranges: List[HeroDuplicateRange] = Field(default_factory=list)

    # Premium packs (one per hero, single tier)
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
    shared_cards: List[Any] = Field(default_factory=list, description="Gold/Blue/Gray shared cards")
    coins: int = Field(default=0)
    total_bluestars: int = Field(default=0)
    pity_counter: int = Field(default=0, description="Pulls since last hero card")
    last_hero_pulled: Optional[str] = Field(default=None, description="hero_id of last hero card pull (for anti-streak)")
    hero_streak_count: int = Field(default=0, description="Consecutive pulls of the same hero")
    # Shared hero XP (one level for all heroes)
    shared_hero_xp: int = Field(default=0)
    shared_hero_level: int = Field(default=1)
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

    # Variant B specific — shared hero XP
    shared_hero_level: int = 0
    shared_hero_xp_today: int = 0
    hero_xp_today: Dict[str, int] = field(default_factory=dict)
    hero_levels: Dict[str, int] = field(default_factory=dict)
    hero_card_avg_levels: Dict[str, float] = field(default_factory=dict)
    skill_nodes_unlocked_today: Dict[str, int] = field(default_factory=dict)
    cards_unlocked_today: int = 0
    jokers_received_today: int = 0
    jokers_used_today: int = 0
    premium_packs_opened: int = 0
    premium_diamonds_spent: int = 0
    hero_tokens_received: int = 0

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
    final_shared_hero_level: int = Field(default=0)
    final_shared_hero_xp: int = Field(default=0)
    final_hero_levels: Dict[str, int] = Field(default_factory=dict)
    final_hero_xp: Dict[str, int] = Field(default_factory=dict)
    total_premium_diamonds_spent: int = Field(default=0)
    total_jokers_received: int = Field(default=0)
    total_hero_tokens: int = Field(default=0)
