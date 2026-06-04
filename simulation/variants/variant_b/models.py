"""Variant B data models — Hero Card System.

All models are Pydantic BaseModels so every field is editable from the frontend.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


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
    token_cost: int = Field(default=0, description="Hero Tokens required to activate this node (skill tree upgrade cost)")


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
    min_amount: int = Field(default=1, description="Minimum reward amount (inclusive)")
    max_amount: int = Field(default=1, description="Maximum reward amount (inclusive)")
    probability: float = Field(default=0.10, description="Chance of this reward dropping per pack")

    @model_validator(mode="before")
    @classmethod
    def _legacy_amount(cls, data):
        # Backward compat: legacy `amount` field becomes both min and max.
        if isinstance(data, dict) and "amount" in data:
            amt = data.pop("amount")
            data.setdefault("min_amount", amt)
            data.setdefault("max_amount", amt)
        return data

    @model_validator(mode="after")
    def _ensure_range(self):
        if self.max_amount < self.min_amount:
            self.max_amount = self.min_amount
        return self


class PremiumPackPullRarity(BaseModel):
    """Rarity weights for a specific pull position in a premium pack."""
    gray_weight: float = Field(default=0.64)
    blue_weight: float = Field(default=0.30)
    gold_weight: float = Field(default=0.06)


class PremiumPackDef(BaseModel):
    """Definition of a hero-specific premium card pack (single tier per hero).

    New (Hero Unique Pack) structure:
      - 5 MainUpgradeCards (100% rate, dupes = 100-110% of required, per rarity)
      - 1-3 BonusCards (100% rate, dupes = 20-40% of required, per rarity)
      - 2-10 HeroUniqueJoker (25% pack-level probability)
      - 700-2000 Coins (100% pack-level probability)
      - 50-100 HeroTokens (100% pack-level probability)
    Rarity for each card pull follows pull_rarity_schedule indexed by
    PullSinceUniqueGold (1..N). Once a gold is pulled, default_rarity_weights
    apply to all subsequent pulls in the pack.
    """
    pack_id: str
    name: str
    featured_hero_ids: List[str] = Field(description="Hero(es) whose cards are in this pack")
    card_drop_rates: List[PremiumPackCardRate] = Field(
        default_factory=list,
        description="Legacy per-card drop rates (ignored when pull_rarity_schedule is set)"
    )
    diamond_cost: int = Field(default=500, description="Price in diamonds")

    # ---------- Legacy fields (kept for backward-compat with saved configs) ----------
    min_cards_per_pack: int = Field(default=4, description="[Legacy] Min cards drawn per pack")
    max_cards_per_pack: int = Field(default=8, description="[Legacy] Max cards drawn per pack")
    joker_rate: float = Field(default=0.0, description="[Legacy] Per-draw joker chance (use joker_probability instead)")
    gold_guarantee: bool = Field(default=False, description="[Legacy] Force-gold guarantee (not used by new flow)")
    hero_tokens_per_pack: int = Field(default=0, description="[Legacy] Fixed Hero Tokens per pack (use hero_tokens_min/max instead)")
    additional_rewards: List[PremiumPackAdditionalReward] = Field(
        default_factory=list,
        description="[Legacy] Extra probability-based rewards (Coins/HeroTokens are now first-class fields)"
    )
    dupe_pct_per_rarity: Dict[str, float] = Field(
        default_factory=dict,
        description="[Legacy] Single-% per-rarity dupe override (use main_dupe_*_pct + bonus_dupe_*_pct instead)"
    )

    # ---------- New: MainUpgradeCards ----------
    main_cards_min: int = Field(default=5, description="Min MainUpgradeCards per pack")
    main_cards_max: int = Field(default=5, description="Max MainUpgradeCards per pack")
    main_dupe_min_pct: Dict[str, float] = Field(
        default_factory=lambda: {"GRAY": 1.0, "BLUE": 1.0, "GOLD": 1.0},
        description="Per-rarity min % of required dupes for MainUpgradeCards",
    )
    main_dupe_max_pct: Dict[str, float] = Field(
        default_factory=lambda: {"GRAY": 1.1, "BLUE": 1.1, "GOLD": 1.1},
        description="Per-rarity max % of required dupes for MainUpgradeCards",
    )

    # ---------- New: BonusCards ----------
    bonus_cards_min: int = Field(default=1, description="Min BonusCards per pack")
    bonus_cards_max: int = Field(default=3, description="Max BonusCards per pack")
    bonus_dupe_min_pct: Dict[str, float] = Field(
        default_factory=lambda: {"GRAY": 0.2, "BLUE": 0.2, "GOLD": 0.2},
        description="Per-rarity min % of required dupes for BonusCards",
    )
    bonus_dupe_max_pct: Dict[str, float] = Field(
        default_factory=lambda: {"GRAY": 0.4, "BLUE": 0.4, "GOLD": 0.4},
        description="Per-rarity max % of required dupes for BonusCards",
    )

    # ---------- New: pack-level rewards ----------
    joker_probability: float = Field(default=0.25, description="Pack-level chance any HeroUniqueJokers drop")
    joker_min: int = Field(default=2, description="Min jokers when they drop")
    joker_max: int = Field(default=10, description="Max jokers when they drop")

    coins_probability: float = Field(default=1.0, description="Pack-level chance Coins drop")
    coins_min: int = Field(default=700, description="Min Coins when they drop")
    coins_max: int = Field(default=2000, description="Max Coins when they drop")

    hero_tokens_probability: float = Field(default=1.0, description="Pack-level chance HeroTokens drop")
    hero_tokens_min: int = Field(default=50, description="Min HeroTokens when they drop")
    hero_tokens_max: int = Field(default=100, description="Max HeroTokens when they drop")

    # ---------- Rarity schedule (PullSinceUniqueGold = 1..N, then default after gold) ----------
    pull_rarity_schedule: List[PremiumPackPullRarity] = Field(
        default_factory=list,
        description="Rarity weights indexed by PullSinceUniqueGold (1..N). After gold is pulled, uses default_rarity_weights."
    )
    default_rarity_weights: PremiumPackPullRarity = Field(
        default_factory=PremiumPackPullRarity,
        description="Rarity weights after a gold has been pulled (PullSinceUniqueGold counter applies to fresh pull stream)"
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
    hero_vs_shared_base_rate: float = Field(default=0.6, description="Base probability of hero card vs shared card")

    # Hero bucket selection weights (heroes ranked by level, divided into 3 tiers)
    bucket_bottom_weight: float = Field(default=0.40, description="Probability of selecting from lowest-level hero bucket")
    bucket_middle_weight: float = Field(default=0.35, description="Probability of selecting from mid-level hero bucket")
    bucket_top_weight: float = Field(default=0.25, description="Probability of selecting from highest-level hero bucket")

    # Rarity roll weights for hero card drops (New Algo: 7% Gray / 39% Blue / 54% Gold)
    rarity_weight_gray: float = Field(default=0.07, description="Probability of dropping a GRAY card")
    rarity_weight_blue: float = Field(default=0.39, description="Probability of dropping a BLUE card")
    rarity_weight_gold: float = Field(default=0.54, description="Probability of dropping a GOLD card")

    # Anti-streak decay (New Algo): hero axis uses 0.8^StreakHero, the rarity,
    # card, and shared-color axes use 0.6^Streak.
    streak_decay_shared: float = Field(default=0.6, description="Weight decay per consecutive shared pull of the same category (StreakColor)")
    streak_decay_hero: float = Field(default=0.8, description="Weight decay per consecutive pull of the same hero (StreakHero)")
    streak_decay_rarity: float = Field(default=0.6, description="Weight decay per consecutive hero-card pull of the same rarity (StreakColor)")
    streak_decay_card: float = Field(default=0.6, description="Weight decay per consecutive pull of the same hero card (StreakCard)")

    # Shared-card candidate pool: only the N lowest-level shared cards are
    # eligible for a shared pull (New Algo: "Top 33 Lowest Level Shared Cards").
    shared_top_k: int = Field(default=33, description="Number of lowest-level shared cards eligible per shared pull")


# ---------------------------------------------------------------------------
# Bluestar -> power curve (editable tier table)
# ---------------------------------------------------------------------------

class BluestarPowerTier(BaseModel):
    """One bluestar->power tier: every bluestar in `(min_bluestar, max_bluestar]`
    multiplies total power by `multiplier`. Tiers are expected to be contiguous
    (each tier's `min_bluestar` equals the previous tier's `max_bluestar`)."""
    tier: int = Field(description="Tier index (1-based, display only)")
    min_bluestar: float = Field(description="Lower bound (exclusive)")
    max_bluestar: float = Field(description="Upper bound (inclusive)")
    multiplier: float = Field(description="Per-bluestar power multiplier in this tier")


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
        description="Day threshold -> hero_ids unlocked once game_state.day "
                    "reaches that day (fixed calendar: woody day 0 … munara day 802)"
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

    # When True, skill-tree nodes activate purely on the hero-level gate and the
    # HeroToken affordability check is skipped. Used to measure pure Hero Token
    # *demand* — the tokens a player would need to buy every Hero Path node they
    # have unlocked — decoupled from how many tokens they actually earn.
    unlimited_hero_tokens: bool = Field(default=False, description="Skip the HeroToken cost gate on skill-tree nodes (demand analysis)")

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
    # Deprecated: premium packs are always available; field retained so old
    # saved profiles still validate.
    premium_pack_schedule: List[PremiumPackSchedule] = Field(default_factory=list)
    premium_pack_purchase_schedule: List[Dict[str, int]] = Field(
        default_factory=list,
        description="Simulated player purchases: [{pack_id: count_bought}, ...] per day"
    )

    # Pack bonus item economy (per-pack slots, drop probs, base amounts,
    # variance multipliers, and dupe boost). Defaults are populated from
    # simulation.variants.variant_b.pack_bonuses at config-load time.
    pack_bonus_slots: Dict[str, int] = Field(default_factory=dict)
    pack_bonus_probs: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    pack_bonus_amounts: Dict[str, Dict[str, int]] = Field(default_factory=dict)
    pack_bonus_variance: Dict[str, List[float]] = Field(
        default_factory=dict,
        description="pack_name -> [bottom, top] uniform multiplier",
    )
    pack_dupe_boost: Dict[str, List[float]] = Field(
        default_factory=dict,
        description="pack_name -> [shared_card_boost, unique_card_boost]",
    )

    # Shared subsystems (reuse existing models from Variant A)
    pet_system_config: Optional[Any] = None
    gear_system_config: Optional[Any] = None

    # Cohort-driven chapter cadence. One entry per CSV day (day 0 → index 0,
    # mapped onto sim day N via `(N - 1) % len`). The orchestrator opens an
    # EndOfChapterPack per chapter beaten, mirroring the day-by-day simulator
    # and `scripted_runner.run_one_day`.
    chapters_per_day: List[int] = Field(
        default_factory=list,
        description="Per-day chapter completion counts. Mapped to sim day N via (N-1) % len. Used by the day-by-day simulator only.",
    )

    # Bluestar thresholds per chapter (1-indexed via list position: index 0 →
    # chapter 1). The big simulator beats chapter N at the end of the day on
    # which `total_bluestars` first crosses `chapter_bluestar_thresholds[N-1]`.
    # Source: CSV `avg_bs` per chapter. When this list is empty the simulator
    # falls back to the legacy calendar `chapters_per_day` schedule.
    chapter_bluestar_thresholds: List[float] = Field(
        default_factory=list,
        description="Bluestars required to beat chapter N (1-indexed by list position). Drives chapter beating in the big simulator.",
    )

    # Bluestar -> power conversion. Each tier covers (min_bluestar, max_bluestar]
    # and multiplies total power by `multiplier` per bluestar in that range; total
    # power = product over tiers of multiplier ** (bluestars in tier). Editable in
    # the Configuration > Power curve tab. When empty, the default table file
    # (data/defaults/variant_b_bluestar_power_table.json) is used.
    bluestar_power_table: List[BluestarPowerTier] = Field(
        default_factory=list,
        description="Bluestar->power tier table. Contiguous tiers; multiplier applied per bluestar in (min, max].",
    )


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


# Default gear slots attached to every hero. A small fixed set keeps the
# Variant B pet/gear system simple compared to Variant A's 6-slot global gear.
HERO_GEAR_SLOTS: List[str] = ["weapon", "armor", "accessory"]


class HeroPetState(BaseModel):
    """Per-hero pet progression (Variant B).

    Distinct from Variant A's PetState — Variant B's pet model is simpler:
    one pet attached to each hero, levelled by opening PetPacks. Tracks
    `level` (1..max), `xp` toward the next level, and lifetime `pet_packs_opened`.
    """
    level: int = Field(default=1, description="Pet level (1..max_level)")
    xp: int = Field(default=0, description="XP accumulated toward next level")
    pet_packs_opened: int = Field(default=0, description="Lifetime PetPacks credited to this hero")


class HeroGearState(BaseModel):
    """Per-hero gear progression (Variant B).

    Each hero has its own small set of gear slots (HERO_GEAR_SLOTS). Opening
    a GearPack against a hero increments one slot at a time (round-robin),
    so progression spreads evenly across the slots.
    """
    slot_levels: Dict[str, int] = Field(
        default_factory=lambda: {slot: 1 for slot in HERO_GEAR_SLOTS},
        description="slot_name -> level",
    )
    gear_packs_opened: int = Field(default=0, description="Lifetime GearPacks credited to this hero")
    next_slot_index: int = Field(
        default=0,
        description="Round-robin index into HERO_GEAR_SLOTS for the next upgrade",
    )


class HeroProgressState(BaseModel):
    """Runtime state of a single hero."""
    hero_id: str
    xp: int = Field(default=0)
    level: int = Field(default=1)
    skill_tree_progress: int = Field(default=0, description="Index of last unlocked node")
    cards: Dict[str, HeroCardState] = Field(default_factory=dict, description="card_id -> state")
    joker_count: int = Field(default=0, description="Hero joker wildcards available")
    pet: HeroPetState = Field(default_factory=HeroPetState, description="Per-hero pet progression")
    gear: HeroGearState = Field(default_factory=HeroGearState, description="Per-hero gear progression")


class HeroCardGameState(BaseModel):
    """Complete runtime game state for Variant B."""
    day: int = Field(default=0)
    heroes: Dict[str, HeroProgressState] = Field(default_factory=dict)
    shared_cards: List[Any] = Field(default_factory=list, description="Gold/Blue/Gray shared cards")
    coins: int = Field(default=0)
    total_bluestars: int = Field(default=0)
    last_hero_pulled: Optional[str] = Field(default=None, description="hero_id of last hero card pull (StreakHero)")
    hero_streak_count: int = Field(default=0, description="Consecutive pulls of the same hero")
    last_rarity_pulled: Optional[str] = Field(default=None, description="Rarity of last hero card pull (StreakColor)")
    rarity_streak_count: int = Field(default=0, description="Consecutive hero-card pulls of the same rarity")
    last_card_pulled: Optional[str] = Field(default=None, description="'hero_id:card_id' of last hero card pull (StreakCard)")
    card_streak_count: int = Field(default=0, description="Consecutive pulls of the same hero card")
    last_shared_category: Optional[str] = Field(default=None, description="Category of last shared pull (StreakColor)")
    shared_category_streak_count: int = Field(default=0, description="Consecutive shared pulls of the same category")
    # Shared hero XP (one level for all heroes)
    shared_hero_xp: int = Field(default=0)
    shared_hero_level: int = Field(default=1)
    # Bonus items rolled from packs and granted by season pass (HeroTokens,
    # Diamonds, S-Stone, SpiritStone, RandomDesign, RandomGear, PetFood, PetEgg,
    # Everstone, PurpleStars). Keyed by the canonical names in pack_bonuses.py.
    bonus_items: Dict[str, int] = Field(default_factory=dict)
    # Cumulative EndOfChapter packs opened across the run (driven by
    # config.chapters_per_day in the orchestrator).
    chapters_beaten: int = Field(default=0, description="Total chapters beaten so far")
    # Tracks the most-recently-unlocked hero, used as the pack-routing target
    # for PetPack / GearPack openings. Falls back to "first unlocked hero" in
    # the routing helper when unset (e.g. starter hero from day-0 schedule).
    last_unlocked_hero: Optional[str] = Field(
        default=None,
        description="hero_id of the most recently unlocked hero (PetPack/GearPack target)",
    )


# ---------------------------------------------------------------------------
# Simulation result models
# ---------------------------------------------------------------------------

@dataclass
class HeroDailySnapshot:
    """Per-hero end-of-day state snapshot.

    Pydantic is overkill here — these are pure value carriers built once per
    hero per day. Stored inside `HeroCardDailySnapshot.hero_states`.
    """
    level: int = 0
    xp: int = 0
    joker_count: int = 0
    cards_by_rarity: Dict[str, int] = field(default_factory=dict)
    total_cards: int = 0
    # Per-hero pet & gear progression (Variant B). pet_level = HeroPetState.level
    # for the hero on this day; gear_levels = {slot_name: level} from
    # HeroGearState.slot_levels. gear_total_level is a convenience scalar
    # (sum of all slot levels) used by Monte Carlo aggregation.
    pet_level: int = 1
    gear_levels: Dict[str, int] = field(default_factory=dict)
    gear_total_level: int = 0


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
    # Bluestars granted directly by premium packs today (not from upgrades).
    premium_bluestars_today: int = 0
    hero_tokens_received: int = 0
    hero_tokens_spent_today: int = 0
    hero_tokens_balance: int = 0
    # Hero Token *demand*: token cost of every skill-tree node whose hero-level
    # gate was newly crossed today, summed across heroes — i.e. the tokens needed
    # to buy all Hero Path content unlocked today, independent of token income.
    # Run with `unlimited_hero_tokens=True` so the hero-level trajectory reflects
    # the "buys everything" path (all unlockable cards come online on schedule).
    hero_token_demand_today: int = 0
    hero_token_demand_by_hero: Dict[str, int] = field(default_factory=dict)

    # Per-hero state (level, xp, jokers, card-dupes-by-rarity, total cards).
    # Keyed by hero_id. Populated for every hero unlocked on this day.
    hero_states: Dict[str, HeroDailySnapshot] = field(default_factory=dict)

    # Chapter cadence (driven by config.chapters_per_day in the orchestrator).
    chapters_beaten_today: int = 0
    chapters_beaten_total: int = 0

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
    total_hero_tokens_spent: int = Field(default=0)
    total_hero_token_demand: int = Field(default=0, description="Lifetime token cost of every Hero Path node unlocked (level-gate met), supply-independent")
    final_hero_tokens_balance: int = Field(default=0)
    final_hero_skill_progress: Dict[str, int] = Field(default_factory=dict)
