"""Config loader for Variant B — Hero Card System.

Provides default configuration with sample heroes, card pools, skill trees,
premium packs, and upgrade tables. All values are editable from the frontend.
"""

from __future__ import annotations

from simulation.variants.variant_b.models import (
    HeroCardConfig,
    HeroCardDef,
    HeroCardRarity,
    HeroDef,
    HeroDropConfig,
    HeroUpgradeCostTable,
    PremiumPackCardRate,
    PremiumPackDef,
    PremiumPackRarity,
    PremiumPackSchedule,
    SkillTreeNode,
)


def load_defaults() -> HeroCardConfig:
    """Load default Variant B configuration with sample heroes."""
    heroes = [
        _create_sample_hero("woodie", "Woodie", num_cards=12),
        _create_sample_hero("suna", "Suna", num_cards=10),
        _create_sample_hero("felorc", "Felorc", num_cards=8),
    ]

    # Sample premium packs
    premium_packs = [
        _create_premium_pack("woodie_bronze", "Woodie Starter Pack", PremiumPackRarity.BRONZE, ["woodie"], heroes, diamond_cost=200, cards_per_pack=3),
        _create_premium_pack("woodie_silver", "Woodie Booster Pack", PremiumPackRarity.SILVER, ["woodie"], heroes, diamond_cost=500, cards_per_pack=5),
        _create_premium_pack("woodie_gold", "Woodie Premium Pack", PremiumPackRarity.GOLD, ["woodie"], heroes, diamond_cost=1000, cards_per_pack=8),
        _create_premium_pack("woodie_platinum", "Woodie Elite Pack", PremiumPackRarity.PLATINUM, ["woodie"], heroes, diamond_cost=2000, cards_per_pack=10),
        _create_premium_pack("woodie_diamond", "Woodie Ultimate Pack", PremiumPackRarity.DIAMOND, ["woodie"], heroes, diamond_cost=5000, cards_per_pack=15),
        _create_premium_pack("fire_fighters", "Fire Fighters Collection", PremiumPackRarity.GOLD, ["suna", "felorc"], heroes, diamond_cost=1500, cards_per_pack=10),
    ]

    return HeroCardConfig(
        num_days=100,
        initial_coins=0,
        initial_bluestars=0,
        heroes=heroes,
        hero_unlock_schedule={
            0: ["woodie"],
            7: ["suna"],
            14: ["felorc"],
        },
        num_gold_cards=9,
        num_blue_cards=14,
        hero_upgrade_tables=_default_upgrade_tables(),
        joker_drop_rate_in_regular_packs=0.01,
        drop_config=HeroDropConfig(
            hero_vs_shared_base_rate=0.60,
            card_selection_mode="lowest_level",
            pity_counter_threshold=10,
        ),
        daily_pack_schedule=[{"regular": 5.0}],
        premium_packs=premium_packs,
        premium_pack_schedule=[
            PremiumPackSchedule(pack_id="woodie_bronze", available_from_day=1, available_until_day=100),
            PremiumPackSchedule(pack_id="woodie_silver", available_from_day=1, available_until_day=100),
            PremiumPackSchedule(pack_id="woodie_gold", available_from_day=7, available_until_day=100),
            PremiumPackSchedule(pack_id="woodie_platinum", available_from_day=14, available_until_day=100),
            PremiumPackSchedule(pack_id="woodie_diamond", available_from_day=30, available_until_day=100),
            PremiumPackSchedule(pack_id="fire_fighters", available_from_day=14, available_until_day=28),
        ],
    )


def _create_sample_hero(hero_id: str, name: str, num_cards: int = 12) -> HeroDef:
    """Create a sample hero with a balanced card pool and linear skill tree."""
    # Distribute cards across rarities: ~40% common, 25% uncommon, 20% rare, 10% epic, 5% legendary
    rarity_dist = [
        (HeroCardRarity.COMMON, max(1, round(num_cards * 0.40))),
        (HeroCardRarity.UNCOMMON, max(1, round(num_cards * 0.25))),
        (HeroCardRarity.RARE, max(1, round(num_cards * 0.20))),
        (HeroCardRarity.EPIC, max(1, round(num_cards * 0.10))),
        (HeroCardRarity.LEGENDARY, max(1, round(num_cards * 0.05))),
    ]

    cards = []
    xp_values = {
        HeroCardRarity.COMMON: 5,
        HeroCardRarity.UNCOMMON: 10,
        HeroCardRarity.RARE: 20,
        HeroCardRarity.EPIC: 40,
        HeroCardRarity.LEGENDARY: 100,
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

    # Starter cards: first 3 common cards
    starter_ids = [c.card_id for c in cards if c.rarity == HeroCardRarity.COMMON][:3]

    # Linear skill tree: unlock cards every 2 levels
    skill_tree = []
    remaining_cards = [c.card_id for c in cards if c.card_id not in starter_ids]
    for node_idx, level_req in enumerate(range(2, 30, 2)):
        if not remaining_cards:
            break
        # Unlock 1-2 cards per node
        unlock_count = min(2, len(remaining_cards))
        unlocked = remaining_cards[:unlock_count]
        remaining_cards = remaining_cards[unlock_count:]
        skill_tree.append(SkillTreeNode(
            node_index=node_idx,
            hero_level_required=level_req,
            cards_unlocked=unlocked,
            perk_label=f"Level {level_req} unlock",
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


def _create_premium_pack(
    pack_id: str,
    name: str,
    rarity: PremiumPackRarity,
    hero_ids: list[str],
    all_heroes: list[HeroDef],
    diamond_cost: int,
    cards_per_pack: int,
) -> PremiumPackDef:
    """Create a premium pack definition with per-card drop rates."""
    # Collect all cards from featured heroes
    all_cards = []
    for hero in all_heroes:
        if hero.hero_id in hero_ids:
            all_cards.extend(hero.card_pool)

    # Assign drop rates inversely proportional to rarity
    rarity_weights = {
        HeroCardRarity.COMMON: 5.0,
        HeroCardRarity.UNCOMMON: 3.0,
        HeroCardRarity.RARE: 2.0,
        HeroCardRarity.EPIC: 1.0,
        HeroCardRarity.LEGENDARY: 0.3,
    }

    card_rates = [
        PremiumPackCardRate(
            card_id=c.card_id,
            drop_rate=rarity_weights.get(c.rarity, 1.0),
        )
        for c in all_cards
    ]

    # Joker rate scales with pack rarity
    joker_rates = {
        PremiumPackRarity.BRONZE: 0.01,
        PremiumPackRarity.SILVER: 0.02,
        PremiumPackRarity.GOLD: 0.03,
        PremiumPackRarity.PLATINUM: 0.05,
        PremiumPackRarity.DIAMOND: 0.08,
    }

    return PremiumPackDef(
        pack_id=pack_id,
        name=name,
        pack_rarity=rarity,
        featured_hero_ids=hero_ids,
        card_drop_rates=card_rates,
        cards_per_pack=cards_per_pack,
        diamond_cost=diamond_cost,
        joker_rate=joker_rates.get(rarity, 0.02),
    )


def _default_upgrade_tables() -> list[HeroUpgradeCostTable]:
    """Create default upgrade cost tables for each rarity."""
    tables = []
    for rarity, base_dupe, base_coin, base_bs, base_xp in [
        (HeroCardRarity.COMMON, 3, 50, 5, 5),
        (HeroCardRarity.UNCOMMON, 5, 100, 10, 10),
        (HeroCardRarity.RARE, 8, 200, 20, 20),
        (HeroCardRarity.EPIC, 12, 400, 40, 40),
        (HeroCardRarity.LEGENDARY, 20, 800, 80, 100),
    ]:
        num_levels = 20
        tables.append(HeroUpgradeCostTable(
            rarity=rarity,
            duplicate_costs=[base_dupe + i * 2 for i in range(num_levels)],
            coin_costs=[base_coin + i * base_coin for i in range(num_levels)],
            bluestar_rewards=[base_bs + i * 3 for i in range(num_levels)],
            xp_rewards=[base_xp + i * 5 for i in range(num_levels)],
        ))
    return tables
