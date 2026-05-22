"""Day-by-day interactive simulator helpers for Variant B (Hero Card System).

Pure Python / no Streamlit. Exposes the per-action primitives the UI needs:
fresh state, evolve a daily pack tier, open a single pack of any name, open
the 4-pack daily bundle, upgrade a single card, and advance the day counter.

Reuses the existing drop algorithm, premium pack opener, joker helpers, and
upgrade engine. The orchestrator's per-day loop is decomposed into per-pack
calls so the user can pace each action manually.
"""

from __future__ import annotations

from random import Random
from typing import Any, Dict, List, Optional, Tuple

from simulation.models import Card, CardCategory
from simulation.variants.variant_b.models import (
    HeroCardConfig,
    HeroCardGameState,
    HeroPackType,
)
from simulation.variants.variant_b.hero_deck import (
    get_unlocked_cards,
    initialize_hero,
)
from simulation.variants.variant_b.drop_algorithm import (
    check_joker_drop,
    compute_hero_duplicates,
    compute_shared_duplicates,
    decide_hero_or_shared,
    get_coins_per_dupe,
    get_shared_coins_per_dupe,
    select_hero_card,
    select_shared_card,
)
from simulation.variants.variant_b.hero_joker import add_jokers
from simulation.variants.variant_b.upgrade_engine import (
    try_upgrade_hero_card,
    try_upgrade_shared_card,
)
from simulation.variants.variant_b.pack_bonuses import (
    get_dupe_boost,
    roll_pack_bonuses,
)


# Pack-evolution matrix. Starting tier -> [(final_tier, cumulative_weight)].
# Source: user spec (Daily packs evolve to a final tier on open).
EVOLUTION_MATRIX: Dict[str, List[Tuple[str, float]]] = {
    "StandardPackT1": [
        ("StandardPackT1", 0.3164),
        ("StandardPackT2", 0.4391),
        ("StandardPackT3", 0.2010),
        ("StandardPackT4", 0.0405),
        ("StandardPackT5", 0.0030),
    ],
    "StandardPackT2": [
        ("StandardPackT2", 0.3336),
        ("StandardPackT3", 0.4559),
        ("StandardPackT4", 0.2004),
        ("StandardPackT5", 0.0101),
    ],
    "StandardPackT3": [
        ("StandardPackT3", 0.4096),
        ("StandardPackT4", 0.5697),
        ("StandardPackT5", 0.0207),
    ],
    "StandardPackT4": [
        ("StandardPackT4", 0.96),
        ("StandardPackT5", 0.04),
    ],
    "StandardPackT5": [
        ("StandardPackT5", 1.0),
    ],
}


# Daily pack bundle (fixed): 1x T2 + 3x T1.
DAILY_BUNDLE: List[str] = ["StandardPackT2", "StandardPackT1", "StandardPackT1", "StandardPackT1"]


def init_extras() -> Dict[str, Any]:
    """Return a fresh extras dict.

    All bonus item counters (HeroTokens, Diamonds, etc.) now live on
    game_state.bonus_items. This dict only holds things that don't fit on
    the game_state model: unopened pack inventory and a misc bucket.
    """
    return {
        "unopened_packs": {},
        "misc": {},
    }


def init_state(config: HeroCardConfig) -> HeroCardGameState:
    """Mint a fresh game state. Mirrors orchestrator._create_initial_state."""
    state = HeroCardGameState(
        day=0,
        coins=config.initial_coins,
        total_bluestars=config.initial_bluestars,
        shared_hero_xp=0,
        shared_hero_level=1,
    )
    for i in range(1, config.num_gold_cards + 1):
        state.shared_cards.append(
            Card(id=f"gold_{i}", name=f"Gold Card {i}", category=CardCategory.GOLD_SHARED)
        )
    for i in range(1, config.num_blue_cards + 1):
        state.shared_cards.append(
            Card(id=f"blue_{i}", name=f"Blue Card {i}", category=CardCategory.BLUE_SHARED)
        )
    for i in range(1, config.num_gray_cards + 1):
        state.shared_cards.append(
            Card(id=f"gray_{i}", name=f"Gray Card {i}", category=CardCategory.GRAY_SHARED)
        )
    for day_str, hero_ids in config.hero_unlock_schedule.items():
        if int(day_str) <= 0:
            for hero_id in hero_ids:
                hero_def = next((h for h in config.heroes if h.hero_id == hero_id), None)
                if hero_def:
                    state.heroes[hero_id] = initialize_hero(hero_def)
    return state


def advance_day(game_state: HeroCardGameState, new_day: int, config: HeroCardConfig) -> List[str]:
    """Set the day and unlock any heroes scheduled for it. Returns log lines."""
    lines: List[str] = []
    game_state.day = new_day
    hero_ids = config.hero_unlock_schedule.get(new_day, [])
    for hero_id in hero_ids:
        if hero_id not in game_state.heroes:
            hero_def = next((h for h in config.heroes if h.hero_id == hero_id), None)
            if hero_def:
                game_state.heroes[hero_id] = initialize_hero(hero_def)
                lines.append(f"Hero unlocked: {hero_def.name}")
    return lines


def evolve_pack_tier(start_tier: str, rng: Random) -> str:
    """Roll the evolution matrix for a starting tier and return the final tier."""
    table = EVOLUTION_MATRIX.get(start_tier)
    if not table:
        return start_tier
    roll = rng.random()
    cumulative = 0.0
    for final_tier, weight in table:
        cumulative += weight
        if roll < cumulative:
            return final_tier
    return table[-1][0]


def _find_pack_type(config: HeroCardConfig, name: str) -> Optional[HeroPackType]:
    for pt in config.pack_types:
        if pt.name == name:
            return pt
    return None


def _card_types_for_count(card_types_table: Dict[int, Any], total_unlocked: int) -> Tuple[int, int]:
    """Floor-match total unlocked count against card_types_table thresholds."""
    if not card_types_table:
        return 1, 3
    matching_keys = [k for k in card_types_table if int(k) <= total_unlocked]
    if not matching_keys:
        best_key = min(card_types_table.keys(), key=lambda k: int(k))
    else:
        best_key = max(matching_keys, key=lambda k: int(k))
    entry = card_types_table[best_key]
    if hasattr(entry, "min"):
        return entry.min, entry.max
    return int(entry.get("min", 1)), int(entry.get("max", 3))


def _count_unlocked_cards(game_state: HeroCardGameState) -> int:
    total = 0
    for hero_state in game_state.heroes.values():
        for card in hero_state.cards.values():
            if card.unlocked:
                total += 1
    return total


def _pick_joker_hero(game_state: HeroCardGameState) -> Optional[str]:
    """Pick the hero with most unlocked cards (matches orchestrator behavior)."""
    best_hero = None
    best_count = -1
    for hero_id, hero_state in game_state.heroes.items():
        count = len(get_unlocked_cards(hero_state))
        if count > best_count:
            best_count = count
            best_hero = hero_id
    return best_hero


def _resolve_card_name(config: HeroCardConfig, hero_id: str, card_id: str) -> str:
    for hero_def in config.heroes:
        if hero_def.hero_id == hero_id:
            for card_def in hero_def.card_pool:
                if card_def.card_id == card_id:
                    return card_def.name
    return card_id


def open_pack_by_name(
    pack_name: str,
    game_state: HeroCardGameState,
    config: HeroCardConfig,
    rng: Random,
    apply_evolution: bool = False,
) -> Dict[str, Any]:
    """Open one pack via the standard drop flow.

    Args:
        pack_name: Pack-type name as it appears in config.pack_types
            (e.g. "StandardPackT1", "HeroPack", "PetPack", "GearPack").
        apply_evolution: If True, evolve the tier via EVOLUTION_MATRIX before opening.
            Only meaningful for StandardPackT1-T5.

    Returns: dict {
        "start_tier": str (or None if not a standard pack),
        "final_tier": str (the actually-opened pack name),
        "cards": [pull dicts],   # per-pull detail for activity feed
        "jokers_received": int,
        "coins_earned": int,
    }
    """
    start_tier = pack_name if pack_name in EVOLUTION_MATRIX else None
    final_name = evolve_pack_tier(pack_name, rng) if (apply_evolution and start_tier) else pack_name

    pt = _find_pack_type(config, final_name)
    if pt and pt.card_types_table:
        total_unlocked = _count_unlocked_cards(game_state)
        min_cards, max_cards = _card_types_for_count(pt.card_types_table, total_unlocked)
    else:
        min_cards, max_cards = 1, 3
    cards_in_pack = rng.randint(min_cards, max_cards)

    # Per-pack duplicate boost (shared cards, unique/hero cards).
    shared_boost, unique_boost = get_dupe_boost(final_name)

    pulls: List[Dict[str, Any]] = []
    jokers_received = 0
    coins_earned = 0

    for _ in range(cards_in_pack):
        pull_type = decide_hero_or_shared(game_state, config, rng)
        if pull_type == "hero":
            game_state.pity_counter = 0
            result = select_hero_card(game_state, config, rng)
            if result:
                hero_id, card_id = result
                if hero_id == game_state.last_hero_pulled:
                    game_state.hero_streak_count += 1
                else:
                    game_state.last_hero_pulled = hero_id
                    game_state.hero_streak_count = 1
                hero_state = game_state.heroes[hero_id]
                card = hero_state.cards.get(card_id)
                if card:
                    level_before = card.level
                    dupes = compute_hero_duplicates(card.level, card.rarity, config, rng, boost=unique_boost)
                    card.duplicates += dupes
                    cpd = get_coins_per_dupe(card.level, card.rarity, config)
                    coin_income = max(1, dupes * cpd)
                    game_state.coins += coin_income
                    coins_earned += coin_income
                    pulls.append({
                        "kind": "hero",
                        "hero_id": hero_id,
                        "card_id": card_id,
                        "card_name": _resolve_card_name(config, hero_id, card_id),
                        "rarity": card.rarity.value,
                        "level_before": level_before,
                        "duplicates_received": dupes,
                        "coins_earned": coin_income,
                    })
            if check_joker_drop(config, rng):
                best_hero = _pick_joker_hero(game_state)
                if best_hero:
                    add_jokers(game_state.heroes[best_hero], 1)
                    jokers_received += 1
        else:
            game_state.pity_counter += 1
            shared_card = select_shared_card(game_state, rng)
            if shared_card:
                level_before = shared_card.level
                cat = shared_card.category.value if hasattr(shared_card.category, "value") else str(shared_card.category)
                dupes = compute_shared_duplicates(shared_card.level, cat, config, rng, boost=shared_boost)
                shared_card.duplicates += dupes
                cpd = get_shared_coins_per_dupe(shared_card.level, cat, config)
                coin_income = max(1, dupes * cpd)
                game_state.coins += coin_income
                coins_earned += coin_income
                pulls.append({
                    "kind": "shared",
                    "card_id": shared_card.id,
                    "card_name": shared_card.name,
                    "category": cat,
                    "level_before": level_before,
                    "duplicates_received": dupes,
                    "coins_earned": coin_income,
                })

    # Roll bonus items for this pack opening and credit to game_state.
    bonuses = roll_pack_bonuses(final_name, rng)
    for item, amount in bonuses.items():
        game_state.bonus_items[item] = game_state.bonus_items.get(item, 0) + amount

    return {
        "start_tier": start_tier if apply_evolution else None,
        "final_tier": final_name,
        "cards": pulls,
        "jokers_received": jokers_received,
        "coins_earned": coins_earned,
        "bonus_items": bonuses,
        "shared_boost": shared_boost,
        "unique_boost": unique_boost,
    }


def open_daily_bundle(
    game_state: HeroCardGameState,
    config: HeroCardConfig,
    rng: Random,
) -> List[Dict[str, Any]]:
    """Open the fixed daily bundle: 1x StandardPackT2 + 3x StandardPackT1, each with evolution."""
    results: List[Dict[str, Any]] = []
    for pack_name in DAILY_BUNDLE:
        results.append(open_pack_by_name(pack_name, game_state, config, rng, apply_evolution=True))
    return results


def upgrade_single_hero_card(
    game_state: HeroCardGameState,
    config: HeroCardConfig,
    hero_id: str,
    card_id: str,
) -> Optional[Tuple[Dict[str, Any], List]]:
    """Thin wrapper around upgrade_engine.try_upgrade_hero_card for the UI."""
    return try_upgrade_hero_card(game_state, config, hero_id, card_id)


def upgrade_single_shared_card(
    game_state: HeroCardGameState,
    config: HeroCardConfig,
    card_id: str,
) -> Optional[Dict[str, Any]]:
    """Thin wrapper around upgrade_engine.try_upgrade_shared_card for the UI."""
    return try_upgrade_shared_card(game_state, config, card_id)
