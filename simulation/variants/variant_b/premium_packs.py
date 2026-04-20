"""Hero-specific premium card pack economics.

Premium packs are diamond-only, rotating availability, FOMO-driven.
Each pack has per-card drop rates. Dupes use the same %-of-cost mechanic as regular pulls.
"""

from __future__ import annotations

from random import Random
from typing import Any, Dict, List, Optional, Tuple

from simulation.variants.variant_b.models import (
    HeroCardConfig,
    HeroCardGameState,
    HeroCardRarity,
    PremiumPackDef,
    PremiumPackSchedule,
)
from simulation.variants.variant_b.drop_algorithm import compute_hero_duplicates


def get_available_packs(
    day: int,
    schedule: List[PremiumPackSchedule],
    pack_defs: List[PremiumPackDef],
) -> List[PremiumPackDef]:
    """Return premium packs available on a given day."""
    available_ids = {
        s.pack_id
        for s in schedule
        if s.available_from_day <= day <= s.available_until_day
    }
    return [p for p in pack_defs if p.pack_id in available_ids]


def _pick_card_weighted(
    card_rates: List[Tuple[str, float]],
    total_weight: float,
    rng: Optional[Random] = None,
) -> Optional[str]:
    """Pick a card_id via weighted random selection."""
    if not card_rates or total_weight <= 0:
        return None
    if rng:
        roll = rng.random() * total_weight
        cumulative = 0.0
        for card_id, rate in card_rates:
            cumulative += rate
            if roll <= cumulative:
                return card_id
        return card_rates[-1][0]
    return max(card_rates, key=lambda x: x[1])[0]


def _resolve_card_info(
    card_id: str, game_state: HeroCardGameState,
) -> Tuple[str, int, Optional[HeroCardRarity]]:
    """Look up hero_id, card_level, card_rarity from game state."""
    for hid, hstate in game_state.heroes.items():
        if card_id in hstate.cards:
            c = hstate.cards[card_id]
            return hid, c.level, c.rarity
    return "", 1, None


def open_premium_pack(
    pack_def: PremiumPackDef,
    game_state: HeroCardGameState,
    config: HeroCardConfig,
    rng: Optional[Random] = None,
) -> List[Dict[str, Any]]:
    """Open a premium pack and return list of pull results.

    Features:
    - Variable card count (min_cards_per_pack to max_cards_per_pack)
    - Gold guarantee: at least one GOLD rarity card per pack
    - Hero tokens gifted per pack
    - Additional probability-based rewards
    Each pull result is a dict: {card_id, hero_id, duplicates, is_joker, reward_type, reward_amount}.
    """
    results: List[Dict[str, Any]] = []

    # Determine card count for this pack
    if rng:
        num_cards = rng.randint(pack_def.min_cards_per_pack, pack_def.max_cards_per_pack)
    else:
        num_cards = (pack_def.min_cards_per_pack + pack_def.max_cards_per_pack) // 2

    # Build weighted card pool from drop rates
    card_rates = [(cr.card_id, cr.drop_rate) for cr in pack_def.card_drop_rates]
    total_weight = sum(r for _, r in card_rates)

    # Identify gold-rarity cards for gold guarantee
    gold_card_ids = set()
    for hid, hstate in game_state.heroes.items():
        for cid, cstate in hstate.cards.items():
            if cstate.rarity == HeroCardRarity.GOLD:
                gold_card_ids.add(cid)

    gold_rates = [(cid, w) for cid, w in card_rates if cid in gold_card_ids]
    gold_total = sum(w for _, w in gold_rates)

    got_gold = False

    for draw in range(num_cards):
        # Check for joker
        if rng:
            is_joker = rng.random() < pack_def.joker_rate
        else:
            is_joker = pack_def.joker_rate > 0.5

        if is_joker:
            results.append({
                "card_id": "__joker__",
                "hero_id": pack_def.featured_hero_ids[0] if pack_def.featured_hero_ids else "",
                "duplicates": 1,
                "is_joker": True,
            })
            continue

        # Gold guarantee: force gold on last card if none yet
        if pack_def.gold_guarantee and draw == num_cards - 1 and not got_gold and gold_rates:
            selected_card_id = _pick_card_weighted(gold_rates, gold_total, rng)
        else:
            selected_card_id = _pick_card_weighted(card_rates, total_weight, rng)

        if not selected_card_id:
            continue

        hero_id, card_level, card_rarity = _resolve_card_info(selected_card_id, game_state)

        if card_rarity == HeroCardRarity.GOLD:
            got_gold = True

        if card_rarity is not None:
            dupes = compute_hero_duplicates(card_level, card_rarity, config, rng)
        else:
            dupes = 1

        results.append({
            "card_id": selected_card_id,
            "hero_id": hero_id,
            "duplicates": dupes,
            "is_joker": False,
        })

    # Hero tokens (always gifted)
    if pack_def.hero_tokens_per_pack > 0:
        results.append({
            "card_id": "__hero_tokens__",
            "hero_id": pack_def.featured_hero_ids[0] if pack_def.featured_hero_ids else "",
            "duplicates": 0,
            "is_joker": False,
            "reward_type": "hero_tokens",
            "reward_amount": pack_def.hero_tokens_per_pack,
        })

    # Additional probability-based rewards
    for reward in pack_def.additional_rewards:
        roll = rng.random() if rng else 0.5
        if roll < reward.probability:
            results.append({
                "card_id": f"__reward_{reward.reward_type}__",
                "hero_id": "",
                "duplicates": 0,
                "is_joker": False,
                "reward_type": reward.reward_type,
                "reward_amount": reward.amount,
            })

    return results


def process_premium_purchases(
    day: int,
    config: HeroCardConfig,
    game_state: HeroCardGameState,
    rng: Optional[Random] = None,
) -> Tuple[List[Dict[str, Any]], int, int, int]:
    """Process all premium pack purchases for a day.

    Returns: (all_pull_results, total_diamonds_spent, jokers_received, hero_tokens_received)
    """
    day_index = (day - 1) % len(config.premium_pack_purchase_schedule) if config.premium_pack_purchase_schedule else -1
    if day_index < 0:
        return [], 0, 0, 0

    purchases = config.premium_pack_purchase_schedule[day_index]
    available = get_available_packs(day, config.premium_pack_schedule, config.premium_packs)
    available_by_id = {p.pack_id: p for p in available}

    all_results: List[Dict[str, Any]] = []
    total_diamonds = 0
    total_jokers = 0
    total_hero_tokens = 0

    for pack_id, count in purchases.items():
        pack_def = available_by_id.get(pack_id)
        if not pack_def or count <= 0:
            continue

        for _ in range(count):
            pulls = open_premium_pack(pack_def, game_state, config, rng)
            all_results.extend(pulls)
            total_diamonds += pack_def.diamond_cost
            total_jokers += sum(1 for p in pulls if p.get("is_joker", False))
            total_hero_tokens += sum(
                p.get("reward_amount", 0) for p in pulls
                if p.get("reward_type") == "hero_tokens"
            )

    return all_results, total_diamonds, total_jokers, total_hero_tokens
