"""Config loader for Variant B — Hero Card System.

Provides default configuration with sample heroes, card pools, skill trees,
premium packs, and upgrade tables. All values are editable from the frontend.
Supports saving/loading persisted configs to data/defaults/variant_b_config.json.
"""

from __future__ import annotations

import logging
from pathlib import Path

from simulation.variants.variant_b.models import (
    HeroCardConfig,
    HeroCardDef,
    HeroCardRarity,
    HeroDef,
    HeroDuplicateRange,
    HeroDropConfig,
    HeroUpgradeCostTable,
    PremiumPackAdditionalReward,
    PremiumPackCardRate,
    PremiumPackDef,
    PremiumPackSchedule,
    SkillTreeNode,
)


def load_defaults() -> HeroCardConfig:
    """Load Variant B config — from saved file if available, else built-in defaults."""
    saved = load_saved_config()
    if saved is not None:
        return saved
    return _builtin_defaults()


def _builtin_defaults() -> HeroCardConfig:
    """Built-in default Variant B configuration with all 17 heroes (~32 cards each, 544 total)."""
    heroes = [
        _create_sample_hero("woody", "Woody", num_cards=32),
        _create_sample_hero("cowboy", "Cowboy", num_cards=32),
        _create_sample_hero("barbarian", "Barbarian", num_cards=32),
        _create_sample_hero("rexx", "Rexx", num_cards=32),
        _create_sample_hero("sunna", "Sunna", num_cards=32),
        _create_sample_hero("mammon", "Mammon", num_cards=32),
        _create_sample_hero("rogue", "Rogue", num_cards=32),
        _create_sample_hero("felorc", "Felorc", num_cards=32),
        _create_sample_hero("eiva", "Eiva", num_cards=32),
        _create_sample_hero("gudan", "Gudan", num_cards=32),
        _create_sample_hero("druid", "Druid", num_cards=32),
        _create_sample_hero("yasuhiro", "Yasuhiro", num_cards=32),
        _create_sample_hero("nova", "Nova", num_cards=32),
        _create_sample_hero("rickie", "Rickie", num_cards=32),
        _create_sample_hero("raven", "Raven", num_cards=32),
        _create_sample_hero("jester", "Jester", num_cards=32),
        _create_sample_hero("munara", "Munara", num_cards=32),
    ]

    # One premium pack per hero (card pool auto-derived from hero's cards)
    premium_packs = [
        _create_hero_pack(hero) for hero in heroes
    ]

    return HeroCardConfig(
        num_days=100,
        initial_coins=0,
        initial_bluestars=0,
        heroes=heroes,
        hero_unlock_schedule={
            0: ["woody", "cowboy"],
            3: ["barbarian"],
            7: ["rexx", "sunna"],
            10: ["mammon"],
            14: ["rogue", "felorc"],
            18: ["eiva"],
            21: ["gudan", "druid"],
            28: ["yasuhiro"],
            35: ["nova", "rickie"],
            42: ["raven"],
            50: ["jester"],
            60: ["munara"],
        },
        num_gold_cards=9,
        num_blue_cards=14,
        num_gray_cards=20,
        hero_upgrade_tables=_default_upgrade_tables(),
        hero_duplicate_ranges=_default_duplicate_ranges(),
        joker_drop_rate_in_regular_packs=0.01,
        drop_config=HeroDropConfig(
            hero_vs_shared_base_rate=0.50,
            pity_counter_threshold=10,
        ),
        daily_pack_schedule=[{"regular": 5.0}],
        premium_packs=premium_packs,
        premium_pack_schedule=[
            PremiumPackSchedule(pack_id=hero.hero_id, available_from_day=0, available_until_day=100)
            for hero in heroes
        ],
    )


def _create_sample_hero(hero_id: str, name: str, num_cards: int = 32) -> HeroDef:
    """Create a sample hero with a balanced card pool and linear skill tree.

    Default: ~32 cards per hero (17 heroes × 32 = 544 total).
    Rarity distribution is a starting point — fully editable in the UI.
    """
    # Distribute cards across rarities: ~55% gray, 30% blue, 15% gold
    num_gray = max(1, round(num_cards * 0.55))
    num_blue = max(1, round(num_cards * 0.30))
    num_gold = max(1, num_cards - num_gray - num_blue)
    rarity_dist = [
        (HeroCardRarity.GRAY, num_gray),
        (HeroCardRarity.BLUE, num_blue),
        (HeroCardRarity.GOLD, num_gold),
    ]

    cards = []
    xp_values = {
        HeroCardRarity.GRAY: 5,
        HeroCardRarity.BLUE: 15,
        HeroCardRarity.GOLD: 40,
    }
    card_idx = 1
    for rarity, count in rarity_dist:
        for j in range(count):
            cards.append(HeroCardDef(
                card_id=f"{hero_id}_card_{card_idx}",
                hero_id=hero_id,
                rarity=rarity,
                name=f"{name} {rarity.value.title()} {j+1}",
                base_xp_on_upgrade=xp_values[rarity],
            ))
            card_idx += 1

    # Starter cards: first 3 gray cards
    starter_ids = [c.card_id for c in cards if c.rarity == HeroCardRarity.GRAY][:3]

    # Linear skill tree: 33 nodes, distributing remaining cards across them
    # Some nodes unlock cards, others are perk-only nodes
    skill_tree = []
    remaining_cards = [c.card_id for c in cards if c.card_id not in starter_ids]
    num_nodes = 33
    # Spread cards across the first len(remaining_cards) nodes
    for node_idx in range(num_nodes):
        if remaining_cards:
            unlocked = [remaining_cards.pop(0)]
        else:
            unlocked = []
        level_req = 2 + node_idx  # levels 2-34
        skill_tree.append(SkillTreeNode(
            node_index=node_idx,
            hero_level_required=level_req,
            cards_unlocked=unlocked,
            perk_label=f"Level {level_req} unlock" if unlocked else f"Level {level_req} perk",
        ))

    # XP per level: escalating thresholds
    xp_per_level = [50 + i * 25 for i in range(50)]

    return HeroDef(
        hero_id=hero_id,
        name=name,
        card_pool=cards,
        skill_tree=skill_tree,
        xp_per_level=xp_per_level,
        max_level=50,
        starter_card_ids=starter_ids,
    )


def _create_hero_pack(hero: HeroDef) -> PremiumPackDef:
    """Create one premium pack for a hero using their card pool."""
    rarity_weights = {
        HeroCardRarity.GRAY: 5.0,
        HeroCardRarity.BLUE: 2.0,
        HeroCardRarity.GOLD: 1.0,
    }

    card_rates = [
        PremiumPackCardRate(
            card_id=c.card_id,
            drop_rate=rarity_weights.get(c.rarity, 1.0),
        )
        for c in hero.card_pool
    ]

    return PremiumPackDef(
        pack_id=hero.hero_id,
        name=f"{hero.name} Card Pack",
        featured_hero_ids=[hero.hero_id],
        card_drop_rates=card_rates,
        min_cards_per_pack=4,
        max_cards_per_pack=8,
        diamond_cost=500,
        joker_rate=0.02,
        gold_guarantee=True,
        hero_tokens_per_pack=5,
        additional_rewards=[
            PremiumPackAdditionalReward(reward_type="coins", amount=500, probability=0.20),
            PremiumPackAdditionalReward(reward_type="bluestars", amount=50, probability=0.10),
        ],
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
        return HeroCardConfig.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as exc:
        _log.warning("Failed to load saved Variant B config: %s", exc)
        return None


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
            duplicate_costs=[10, 12, 16, 20, 30, 50, 70, 100, 150],
            coin_costs=[250, 375, 500, 625, 750, 875, 1000, 1125, 1250],
            bluestar_rewards=[50, 65, 80, 95, 110, 125, 150, 200, 250],
            xp_rewards=[5, 5, 5, 10, 10, 10, 10, 15, 15],
        ),
        HeroUpgradeCostTable(
            rarity=HeroCardRarity.BLUE,
            duplicate_costs=[10, 12, 16, 20, 30, 50, 70, 100, 150],
            coin_costs=[250, 375, 500, 625, 750, 875, 1000, 1125, 1250],
            bluestar_rewards=[120, 150, 210, 265, 310, 360, 400, 450, 500],
            xp_rewards=[15, 15, 15, 30, 30, 30, 30, 45, 45],
        ),
        HeroUpgradeCostTable(
            rarity=HeroCardRarity.GOLD,
            duplicate_costs=[10, 12, 16, 20, 30, 50, 70, 100, 150],
            coin_costs=[250, 375, 500, 625, 750, 875, 1000, 1125, 1250],
            bluestar_rewards=[150, 200, 250, 300, 350, 400, 500, 600, 750],
            xp_rewards=[40, 40, 40, 75, 75, 75, 75, 150, 150],
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
            coins_per_dupe=[25, 29, 29, 29, 23, 16, 13, 11, 8],
        ),
        HeroDuplicateRange(
            rarity=HeroCardRarity.BLUE,
            min_pct=[0.80, 0.75, 0.70, 0.65, 0.60, 0.55, 0.50, 0.45, 0.40],
            max_pct=[0.90, 0.85, 0.80, 0.75, 0.70, 0.65, 0.60, 0.55, 0.50],
            coins_per_dupe=[25, 29, 29, 29, 23, 16, 13, 11, 8],
        ),
        HeroDuplicateRange(
            rarity=HeroCardRarity.GOLD,
            min_pct=[0.25, 0.25, 0.10, 0.10, 0.10, 0.10, 0.05, 0.05, 0.05],
            max_pct=[0.40, 0.40, 0.15, 0.15, 0.15, 0.15, 0.15, 0.15, 0.15],
            coins_per_dupe=[25, 29, 29, 29, 23, 16, 13, 11, 8],
        ),
    ]
