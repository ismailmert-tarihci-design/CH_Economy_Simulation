"""Config loader for Variant B — Hero Card System.

Provides default configuration with sample heroes, card pools, skill trees,
premium packs, and upgrade tables. All values are editable from the frontend.
Supports saving/loading persisted configs to data/defaults/variant_b_config.json.
"""

from __future__ import annotations

import logging
from pathlib import Path

from simulation.models import UserProfile

from simulation.variants.variant_b.models import (
    HeroCardConfig,
    HeroCardDef,
    HeroCardRarity,
    HeroDef,
    HeroDuplicateRange,
    HeroDropConfig,
    HeroUpgradeCostTable,
    HeroCardTypesRange,
    HeroPackType,
    PremiumPackDef,
    PremiumPackPullRarity,
    SharedDuplicateRange,
    SharedUpgradeCostTable,
    SkillTreeNode,
)
from simulation.variants.variant_b.pack_bonuses import (
    default_pack_bonus_amounts,
    default_pack_bonus_probs,
    default_pack_bonus_slots,
    default_pack_bonus_variance,
    default_pack_dupe_boost,
)


def load_defaults() -> HeroCardConfig:
    """Load Variant B config — from saved file if available, else built-in defaults."""
    saved = load_saved_config()
    if saved is not None:
        return saved
    return _builtin_defaults()


def _builtin_defaults() -> HeroCardConfig:
    """Built-in default Variant B configuration with all 17 heroes (24 cards each, 408 total)."""
    heroes = [
        _create_sample_hero("woody", "Woody"),
        _create_sample_hero("cowboy", "Cowboy"),
        _create_sample_hero("barbarian", "Barbarian"),
        _create_sample_hero("rexx", "Rexx"),
        _create_sample_hero("sunna", "Sunna"),
        _create_sample_hero("mammon", "Mammon"),
        _create_sample_hero("rogue", "Rogue"),
        _create_sample_hero("felorc", "Felorc"),
        _create_sample_hero("eiva", "Eiva"),
        _create_sample_hero("gudan", "Gudan"),
        _create_sample_hero("druid", "Druid"),
        _create_sample_hero("yasuhiro", "Yasuhiro"),
        _create_sample_hero("nova", "Nova"),
        _create_sample_hero("rickie", "Rickie"),
        _create_sample_hero("raven", "Raven"),
        _create_sample_hero("jester", "Jester"),
        _create_sample_hero("munara", "Munara"),
    ]

    # One premium pack per hero (card pool auto-derived from hero's cards)
    premium_packs = [
        _create_hero_pack(hero) for hero in heroes
    ]

    return HeroCardConfig(
        num_days=730,
        initial_coins=0,
        initial_bluestars=0,
        heroes=heroes,
        hero_unlock_schedule={
            # DaysToReach -> hero unlocked (per spec)
            0: ["woody"],        # hero 1
            1: ["cowboy"],       # hero 2
            9: ["barbarian"],    # hero 3
            23: ["rexx"],        # hero 4
            61: ["sunna"],       # hero 5
            86: ["mammon"],      # hero 6
            112: ["rogue"],      # hero 7
            181: ["felorc"],     # hero 8
            250: ["eiva"],       # hero 9
            319: ["gudan"],      # hero 10
            388: ["druid"],      # hero 11
            457: ["yasuhiro"],   # hero 12
            526: ["nova"],       # hero 13
            595: ["rickie"],     # hero 14
            664: ["raven"],      # hero 15
            733: ["jester"],     # hero 16
            802: ["munara"],     # hero 17
        },
        num_gold_cards=9,
        num_blue_cards=14,
        num_gray_cards=6,
        hero_upgrade_tables=_default_upgrade_tables(),
        hero_duplicate_ranges=_default_duplicate_ranges(),
        shared_upgrade_tables=_default_shared_upgrade_tables(),
        shared_duplicate_ranges=_default_shared_duplicate_ranges(),
        shared_xp_per_level=[
            100, 100, 100, 100,
            125, 125, 125,
            150, 150, 150,
            175, 175, 175,
            200, 200,
            250, 250,
            300, 300,
            350, 350,
            400, 400,
            450, 450,
            500, 500, 500, 500,
        ],
        shared_max_hero_level=30,
        joker_drop_rate_in_regular_packs=0.01,
        drop_config=HeroDropConfig(
            hero_vs_shared_base_rate=0.6093,
            pity_counter_threshold=10,
            rarity_weight_gray=0.0673,
            rarity_weight_blue=0.3894,
            rarity_weight_gold=0.5432,
        ),
        pack_types=[
            HeroPackType(name="StandardPackT1", card_types_table={
                0: HeroCardTypesRange(min=1, max=2),
                100: HeroCardTypesRange(min=1, max=2),
                200: HeroCardTypesRange(min=1, max=2),
                350: HeroCardTypesRange(min=1, max=2),
                500: HeroCardTypesRange(min=1, max=2),
            }),
            HeroPackType(name="StandardPackT2", card_types_table={
                0: HeroCardTypesRange(min=1, max=2),
                100: HeroCardTypesRange(min=1, max=2),
                200: HeroCardTypesRange(min=1, max=3),
                350: HeroCardTypesRange(min=1, max=3),
                500: HeroCardTypesRange(min=1, max=3),
            }),
            HeroPackType(name="StandardPackT3", card_types_table={
                0: HeroCardTypesRange(min=1, max=3),
                100: HeroCardTypesRange(min=1, max=3),
                200: HeroCardTypesRange(min=2, max=3),
                350: HeroCardTypesRange(min=2, max=3),
                500: HeroCardTypesRange(min=2, max=3),
            }),
            HeroPackType(name="StandardPackT4", card_types_table={
                0: HeroCardTypesRange(min=1, max=3),
                100: HeroCardTypesRange(min=1, max=3),
                200: HeroCardTypesRange(min=2, max=4),
                350: HeroCardTypesRange(min=2, max=4),
                500: HeroCardTypesRange(min=2, max=4),
            }),
            HeroPackType(name="StandardPackT5", card_types_table={
                0: HeroCardTypesRange(min=3, max=5),
                100: HeroCardTypesRange(min=3, max=5),
                200: HeroCardTypesRange(min=4, max=5),
                350: HeroCardTypesRange(min=4, max=5),
                500: HeroCardTypesRange(min=4, max=5),
            }),
            HeroPackType(name="EndOfChapterPack", card_types_table={
                0: HeroCardTypesRange(min=1, max=2),
                100: HeroCardTypesRange(min=1, max=2),
                200: HeroCardTypesRange(min=1, max=2),
                350: HeroCardTypesRange(min=1, max=2),
                500: HeroCardTypesRange(min=1, max=2),
            }),
            HeroPackType(name="PetPack", card_types_table={
                0: HeroCardTypesRange(min=1, max=2),
                100: HeroCardTypesRange(min=1, max=2),
                200: HeroCardTypesRange(min=2, max=3),
                350: HeroCardTypesRange(min=2, max=3),
                500: HeroCardTypesRange(min=2, max=4),
            }),
            HeroPackType(name="HeroPack", card_types_table={
                0: HeroCardTypesRange(min=1, max=2),
                100: HeroCardTypesRange(min=1, max=2),
                200: HeroCardTypesRange(min=2, max=3),
                350: HeroCardTypesRange(min=2, max=3),
                500: HeroCardTypesRange(min=2, max=4),
            }),
            HeroPackType(name="GearPack", card_types_table={
                0: HeroCardTypesRange(min=1, max=2),
                100: HeroCardTypesRange(min=1, max=2),
                200: HeroCardTypesRange(min=2, max=3),
                350: HeroCardTypesRange(min=2, max=3),
                500: HeroCardTypesRange(min=2, max=4),
            }),
        ],
        daily_pack_schedule=[
            {
                "StandardPackT1": 1.0, "StandardPackT2": 1.0, "StandardPackT3": 1.0,
                "StandardPackT4": 1.0, "StandardPackT5": 1.0,
                "PetPack": 1.0, "GearPack": 1.0, "HeroPack": 1.0,
                "EndOfChapterPack": 1.0,
            },
        ],
        premium_packs=premium_packs,
        premium_pack_schedule=[],
        pack_bonus_slots=default_pack_bonus_slots(),
        pack_bonus_probs=default_pack_bonus_probs(),
        pack_bonus_amounts=default_pack_bonus_amounts(),
        pack_bonus_variance=default_pack_bonus_variance(),
        pack_dupe_boost=default_pack_dupe_boost(),
    )


def _create_sample_hero(hero_id: str, name: str) -> HeroDef:
    """Create a hero with the canonical card pool + skill tree.

    Uniform across all heroes:
      Cards (25 total): 13 Gold, 10 Blue, 2 Gray
      Starters (13):     5 Gold, 6 Blue, 2 Gray
      Unlockables (12):  8 Gold, 4 Blue, 0 Gray  — granted by skill tree
    """
    # (rarity, total, num_starters)
    rarity_spec = [
        (HeroCardRarity.GOLD, 13, 5),
        (HeroCardRarity.BLUE, 10, 6),
        (HeroCardRarity.GRAY, 2, 2),
    ]

    xp_values = {
        HeroCardRarity.GRAY: 5,
        HeroCardRarity.BLUE: 15,
        HeroCardRarity.GOLD: 40,
    }

    cards: list[HeroCardDef] = []
    starter_ids: list[str] = []
    unlockable_queue: list[str] = []
    for rarity, total, starter_count in rarity_spec:
        for j in range(total):
            card_id = f"{hero_id}_{rarity.value.lower()}_{j+1}"
            cards.append(HeroCardDef(
                card_id=card_id,
                hero_id=hero_id,
                rarity=rarity,
                name=f"{name} {rarity.value.title()} {j+1}",
                base_xp_on_upgrade=xp_values[rarity],
            ))
            if j < starter_count:
                starter_ids.append(card_id)
            else:
                unlockable_queue.append(card_id)

    # Skill tree (levels 2-30, 29 nodes; level 1 has no reward).
    # 12 "Unlockable Card" entries consume the 12 unlockable cards in order.
    #
    # Token costs follow Ivan's perk-type-keyed scheme:
    #   - Stat Boosts Only       : free (first two bonus stat levels)
    #   - Unlockable Card        : 250 (1st pull), 500 (2nd pull), 1000 thereafter
    #   - +1 Battle Deck Size    : 750 (first), 1000 (subsequent)
    #   - Hero Passive           : 1000 (first), 1500 (subsequent)
    #   - Perma Slot Upgrade     : 2000
    #   - All Heroes Stat Boost  : 2000
    #   - Ascension Shards       : 5000
    _TREE_TEMPLATE = [
        # (level, reward_type)
        (2,  "Stat Boosts Only"),
        (3,  "Stat Boosts Only"),
        (4,  "Unlockable Card"),
        (5,  "Unlockable Card"),
        (6,  "Hero Passive"),
        (7,  "Unlockable Card"),
        (8,  "Unlockable Card"),
        (9,  "Hero Passive"),
        (10, "Unlockable Card"),
        (11, "+1 Battle Deck Size"),
        (12, "Unlockable Card"),
        (13, "Hero Passive"),
        (14, "Unlockable Card"),
        (15, "Perma Slot Upgrade"),
        (16, "Unlockable Card"),
        (17, "Hero Passive"),
        (18, "Unlockable Card"),
        (19, "+1 Battle Deck Size"),
        (20, "Unlockable Card"),
        (21, "Unlockable Card"),
        (22, "Hero Passive"),
        (23, "Unlockable Card"),
        (24, "All Heroes Stat Boost"),
        (25, "Ascension Shards"),
        (26, "All Heroes Stat Boost"),
        (27, "Ascension Shards"),
        (28, "All Heroes Stat Boost"),
        (29, "Ascension Shards"),
        (30, "All Heroes Stat Boost"),
    ]

    def _token_cost_for(perk: str, occurrence: int) -> int:
        # `occurrence` is 1-indexed: the Nth time we've seen this perk type.
        if perk == "Stat Boosts Only":
            return 0
        if perk == "Unlockable Card":
            if occurrence == 1:
                return 250
            if occurrence == 2:
                return 500
            return 1000
        if perk == "+1 Battle Deck Size":
            return 750 if occurrence == 1 else 1000
        if perk == "Hero Passive":
            return 1000 if occurrence == 1 else 1500
        if perk == "Perma Slot Upgrade":
            return 2000
        if perk == "All Heroes Stat Boost":
            return 2000
        if perk == "Ascension Shards":
            return 5000
        return 0

    _perk_counts: dict[str, int] = {}

    skill_tree: list[SkillTreeNode] = []
    queue = list(unlockable_queue)
    for node_idx, (level_req, reward_type) in enumerate(_TREE_TEMPLATE):
        cards_unlocked: list[str] = []
        if reward_type == "Unlockable Card":
            if not queue:
                raise RuntimeError(
                    f"{hero_id}: skill tree expects more Unlockable Card slots than available "
                    f"unlockable cards (got {len(unlockable_queue)})"
                )
            cards_unlocked = [queue.pop(0)]
        _perk_counts[reward_type] = _perk_counts.get(reward_type, 0) + 1
        token_cost = _token_cost_for(reward_type, _perk_counts[reward_type])
        skill_tree.append(SkillTreeNode(
            node_index=node_idx,
            hero_level_required=level_req,
            cards_unlocked=cards_unlocked,
            perk_label=reward_type,
            token_cost=token_cost,
        ))
    if queue:
        raise RuntimeError(
            f"{hero_id}: {len(queue)} unlockable cards left unassigned by skill tree"
        )

    # XP per level (29 entries: XP to go from level 1->2, 2->3, ..., 29->30)
    xp_per_level = [
        100, 100, 100, 100,        # levels 2..5
        125, 125, 125,             # levels 6..8
        150, 150, 150,             # levels 9..11
        175, 175, 175,             # levels 12..14
        200, 200,                  # levels 15..16
        250, 250,                  # levels 17..18
        300, 300,                  # levels 19..20
        350, 350,                  # levels 21..22
        400, 400,                  # levels 23..24
        450, 450,                  # levels 25..26
        500, 500, 500, 500,        # levels 27..30
    ]

    return HeroDef(
        hero_id=hero_id,
        name=name,
        card_pool=cards,
        skill_tree=skill_tree,
        xp_per_level=xp_per_level,
        max_level=30,
        starter_card_ids=starter_ids,
    )


def _create_hero_pack(hero: HeroDef) -> PremiumPackDef:
    """Create one Hero Unique Pack for a hero.

    Composition:
      - 5 MainUpgradeCards (100% rate, 100-110% of required dupes per rarity)
      - 1-3 BonusCards     (100% rate, 20-40% of required dupes per rarity)
      - 2-10 HeroUniqueJokers @ 25% pack probability
      - 700-2000 Coins @ 100%
      - 50-100 HeroTokens @ 100%

    PullSinceUniqueGold rarity table: Grey 9/7/5/2%, Blue 40/33/23/12%, Gold 51/60/72/86%.
    After gold: Grey 45%, Blue 35%, Gold 20%.
    """
    return PremiumPackDef(
        pack_id=hero.hero_id,
        name=f"{hero.name} Card Pack",
        featured_hero_ids=[hero.hero_id],
        diamond_cost=500,
        main_cards_min=5,
        main_cards_max=5,
        main_dupe_min_pct={"GRAY": 1.0, "BLUE": 1.0, "GOLD": 1.0},
        main_dupe_max_pct={"GRAY": 1.1, "BLUE": 1.1, "GOLD": 1.1},
        bonus_cards_min=1,
        bonus_cards_max=3,
        bonus_dupe_min_pct={"GRAY": 0.2, "BLUE": 0.2, "GOLD": 0.2},
        bonus_dupe_max_pct={"GRAY": 0.4, "BLUE": 0.4, "GOLD": 0.4},
        joker_probability=0.25,
        joker_min=2,
        joker_max=10,
        coins_probability=1.0,
        coins_min=700,
        coins_max=2000,
        hero_tokens_probability=1.0,
        hero_tokens_min=50,
        hero_tokens_max=100,
        pull_rarity_schedule=[
            PremiumPackPullRarity(gray_weight=0.09, blue_weight=0.40, gold_weight=0.51),
            PremiumPackPullRarity(gray_weight=0.07, blue_weight=0.33, gold_weight=0.60),
            PremiumPackPullRarity(gray_weight=0.05, blue_weight=0.23, gold_weight=0.72),
            PremiumPackPullRarity(gray_weight=0.02, blue_weight=0.12, gold_weight=0.86),
        ],
        default_rarity_weights=PremiumPackPullRarity(gray_weight=0.45, blue_weight=0.35, gold_weight=0.20),
    )


_log = logging.getLogger(__name__)


def _get_saved_config_path() -> Path:
    """Path to the persisted Variant B config file."""
    return Path(__file__).resolve().parent.parent.parent.parent / "data" / "defaults" / "variant_b_config.json"


def load_saved_config() -> HeroCardConfig | None:
    """Load persisted Variant B config from disk, or None if not found."""
    path = _get_saved_config_path()
    if not path.exists():
        return None
    try:
        cfg = HeroCardConfig.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as exc:
        _log.warning("Failed to load saved Variant B config: %s", exc)
        return None
    # Backfill pack-bonus tables for configs persisted before they existed on the model.
    if not cfg.pack_bonus_slots:
        cfg.pack_bonus_slots = default_pack_bonus_slots()
    if not cfg.pack_bonus_probs:
        cfg.pack_bonus_probs = default_pack_bonus_probs()
    if not cfg.pack_bonus_amounts:
        cfg.pack_bonus_amounts = default_pack_bonus_amounts()
    if not cfg.pack_bonus_variance:
        cfg.pack_bonus_variance = default_pack_bonus_variance()
    if not cfg.pack_dupe_boost:
        cfg.pack_dupe_boost = default_pack_dupe_boost()
    return cfg


def save_config(config: HeroCardConfig) -> None:
    """Persist the current Variant B config to disk."""
    path = _get_saved_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(config.model_dump_json(indent=2), encoding="utf-8")


def _default_upgrade_tables() -> list[HeroUpgradeCostTable]:
    """Create default upgrade cost tables for each rarity (9 card levels)."""
    return [
        HeroUpgradeCostTable(
            rarity=HeroCardRarity.GRAY,
            duplicate_costs=[20, 30, 40, 80, 100, 120, 140, 210, 270],
            coin_costs=[250, 375, 500, 625, 750, 875, 1000, 1125, 1250],
            bluestar_rewards=[40, 50, 50, 80, 100, 100, 120, 150, 180],
            xp_rewards=[10, 10, 10, 20, 20, 20, 20, 30, 30],
        ),
        HeroUpgradeCostTable(
            rarity=HeroCardRarity.BLUE,
            duplicate_costs=[50, 75, 100, 140, 175, 210, 245, 385, 495],
            coin_costs=[250, 375, 500, 625, 750, 875, 1000, 1125, 1250],
            bluestar_rewards=[100, 125, 125, 140, 175, 175, 210, 275, 330],
            xp_rewards=[25, 25, 25, 35, 35, 35, 35, 55, 55],
        ),
        HeroUpgradeCostTable(
            rarity=HeroCardRarity.GOLD,
            duplicate_costs=[60, 90, 140, 220, 275, 330, 385, 560, 720],
            coin_costs=[250, 375, 500, 625, 750, 875, 1000, 1125, 1250],
            bluestar_rewards=[120, 150, 175, 220, 275, 275, 330, 400, 480],
            xp_rewards=[30, 30, 35, 55, 55, 55, 55, 80, 80],
        ),
    ]


def _default_duplicate_ranges() -> list[HeroDuplicateRange]:
    """Default duplicate % ranges for hero card pulls, per rarity.

    When a hero card is pulled, dupes received = round(dupe_cost_for_next_level * pct),
    where pct is drawn uniformly from [min_pct, max_pct] for that card's current level.

    Percentages decrease as card level increases — early levels are easier to upgrade.
    9 entries (one per card level, index 0 = level 1).
    """
    return [
        HeroDuplicateRange(
            rarity=HeroCardRarity.GRAY,
            min_pct=[0.80, 0.75, 0.70, 0.65, 0.60, 0.55, 0.50, 0.45, 0.40],
            max_pct=[0.90, 0.85, 0.80, 0.75, 0.70, 0.65, 0.60, 0.55, 0.50],
            coins_per_dupe=[13, 12, 12, 8, 7, 7, 7, 5, 5],
        ),
        HeroDuplicateRange(
            rarity=HeroCardRarity.BLUE,
            min_pct=[0.60, 0.55, 0.50, 0.45, 0.40, 0.40, 0.40, 0.40, 0.40],
            max_pct=[0.70, 0.65, 0.60, 0.55, 0.50, 0.50, 0.50, 0.50, 0.50],
            coins_per_dupe=[5, 5, 5, 5, 4, 4, 4, 3, 3],
        ),
        HeroDuplicateRange(
            rarity=HeroCardRarity.GOLD,
            min_pct=[0.55, 0.50, 0.45, 0.40, 0.40, 0.40, 0.40, 0.40, 0.40],
            max_pct=[0.65, 0.60, 0.55, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50],
            coins_per_dupe=[5, 4, 4, 3, 3, 3, 3, 2, 2],
        ),
    ]


def _default_shared_upgrade_tables() -> list[SharedUpgradeCostTable]:
    """Default upgrade cost tables for shared cards (99 levels per category).

    Shared card upgrades grant bluestars but NO hero XP.
    """
    num_levels = 99

    coin_costs = [50 + 50 * i for i in range(num_levels)]  # 50, 100, ..., 4950

    # Gold Shared: dupes 60, 75, 90... (+15 per level)
    gold_dupes = [60 + 15 * i for i in range(num_levels)]
    gold_bluestars = (
        [30] * 4 + [35] * 5 + [40] * 5 + [45] * 5 + [50] * 5 + [55] * 5 +
        [60] * 6 + [65] * 6 + [70] * 6 + [75] * 6 + [80] * 6 + [85] * 6 +
        [90] * 6 + [95] * 6 + [100] * 6 + [105] * 6 + [110] * 6 + [115] * 4
    )
    assert len(gold_bluestars) == num_levels, f"gold_bluestars len {len(gold_bluestars)}"

    # Blue Shared: dupes 50, 60, 70... (+10 per level)
    blue_dupes = [50 + 10 * i for i in range(num_levels)]
    # Gray Shared: dupes 20, 25, 30... (+5 per level)
    gray_dupes = [20 + 5 * i for i in range(num_levels)]

    # Blue and Gray share the same bluestar reward pattern
    shared_blue_gray_bluestars = (
        [10] * 5 + [15] * 6 + [20] * 6 + [25] * 6 + [30] * 6 + [35] * 6 +
        [40] * 6 + [45] * 7 + [50] * 7 + [55] * 7 + [60] * 7 + [65] * 7 +
        [70] * 7 + [75] * 8 + [80] * 8
    )
    assert len(shared_blue_gray_bluestars) == num_levels, f"blue/gray bluestars len {len(shared_blue_gray_bluestars)}"

    return [
        SharedUpgradeCostTable(
            category="GRAY_SHARED",
            duplicate_costs=gray_dupes,
            coin_costs=coin_costs,
            bluestar_rewards=shared_blue_gray_bluestars,
        ),
        SharedUpgradeCostTable(
            category="BLUE_SHARED",
            duplicate_costs=blue_dupes,
            coin_costs=coin_costs,
            bluestar_rewards=shared_blue_gray_bluestars,
        ),
        SharedUpgradeCostTable(
            category="GOLD_SHARED",
            duplicate_costs=gold_dupes,
            coin_costs=coin_costs,
            bluestar_rewards=gold_bluestars,
        ),
    ]


def _default_shared_duplicate_ranges() -> list[SharedDuplicateRange]:
    """Default duplicate % ranges for shared card pulls, per category.

    99 entries per category (one per card level). Same values for all shared categories.
    """
    # Stepped taper matching the user-specified breakpoints
    shared_min_pct = (
        [0.80] * 10 + [0.70] * 19 + [0.65] * 11 + [0.60] * 9 +
        [0.55] * 11 + [0.50] * 20 + [0.40] * 19
    )
    shared_max_pct = (
        [0.90] * 10 + [0.80] * 19 + [0.75] * 11 + [0.70] * 9 +
        [0.65] * 11 + [0.60] * 20 + [0.60] * 19
    )
    shared_coins = [
        5, 8, 9, 11, 13, 14, 15, 16, 17, 18,
        18, 19, 20, 20, 20, 21, 21, 22, 22, 22,
        23, 23, 23, 23, 24, 24, 24, 24, 24, 24,
        25, 25, 25, 25, 25, 25, 25, 25, 26, 26,
        26, 26, 26, 26, 26, 26, 26, 26, 26, 27,
        27, 27, 27, 27, 27, 27, 27, 27, 27, 27,
        27, 27, 27, 27, 27, 27, 27, 27, 27, 28,
        28, 28, 28, 28, 28, 28, 28, 28, 28, 28,
        28, 28, 28, 28, 28, 28, 28, 28, 28, 28,
        28, 28, 28, 28, 28, 28, 28, 28, 28,
    ]

    return [
        SharedDuplicateRange(
            category="GRAY_SHARED",
            min_pct=shared_min_pct, max_pct=shared_max_pct,
            coins_per_dupe=shared_coins,
        ),
        SharedDuplicateRange(
            category="BLUE_SHARED",
            min_pct=shared_min_pct, max_pct=shared_max_pct,
            coins_per_dupe=shared_coins,
        ),
        SharedDuplicateRange(
            category="GOLD_SHARED",
            min_pct=shared_min_pct, max_pct=shared_max_pct,
            coins_per_dupe=shared_coins,
        ),
    ]


# ── Variant B profile CRUD ───────────────────────────────────────────────────

def _get_vb_profiles_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "data" / "profiles_variant_b"


def list_vb_profiles() -> list[str]:
    d = _get_vb_profiles_dir()
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob("*.json"))


def load_vb_profile(name: str) -> UserProfile:
    path = _get_vb_profiles_dir() / f"{name}.json"
    return UserProfile.model_validate_json(path.read_text(encoding="utf-8"))


def save_vb_profile(profile: UserProfile) -> None:
    d = _get_vb_profiles_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{profile.name}.json"
    path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")


def delete_vb_profile(name: str) -> None:
    path = _get_vb_profiles_dir() / f"{name}.json"
    if path.exists():
        path.unlink()
