"""Hero-specific premium card pack economics.

Premium packs are diamond-only, rotating availability, FOMO-driven.
Each pack has per-card drop rates and optional dupe boost multipliers.
"""

from __future__ import annotations

import math
from random import Random
from typing import Any, Dict, List, Optional, Tuple

from simulation.variants.variant_b.models import (
    HeroCardConfig,
    HeroCardGameState,
    PremiumPackDef,
    PremiumPackSchedule,
)


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


def open_premium_pack(
    pack_def: PremiumPackDef,
    game_state: HeroCardGameState,
    rng: Optional[Random] = None,
) -> List[Dict[str, Any]]:
    """Open a premium pack and return list of pull results.

    Each pull result is a dict: {card_id, hero_id, duplicates, is_joker}
    """
    results: List[Dict[str, Any]] = []

    # Build weighted card pool from drop rates
    card_rates = [(cr.card_id, cr.drop_rate) for cr in pack_def.card_drop_rates]
    total_weight = sum(r for _, r in card_rates)

    for draw in range(pack_def.cards_per_pack):
        # Check for joker
        if rng:
            is_joker = rng.random() < pack_def.joker_rate
        else:
            is_joker = pack_def.joker_rate > 0.5  # deterministic threshold

        if is_joker:
            # Joker pull — applies to first featured hero
            results.append({
                "card_id": "__joker__",
                "hero_id": pack_def.featured_hero_ids[0] if pack_def.featured_hero_ids else "",
                "duplicates": 1,
                "is_joker": True,
            })
            continue

        # Card pull via weighted selection
        if rng and total_weight > 0:
            roll = rng.random() * total_weight
            cumulative = 0.0
            selected_card_id = card_rates[0][0]
            for card_id, rate in card_rates:
                cumulative += rate
                if roll <= cumulative:
                    selected_card_id = card_id
                    break
        elif card_rates:
            # Deterministic: pick highest-weight card (simplified)
            selected_card_id = max(card_rates, key=lambda x: x[1])[0]
        else:
            continue

        # Determine hero_id from game state
        hero_id = ""
        for hid, hstate in game_state.heroes.items():
            if selected_card_id in hstate.cards:
                hero_id = hid
                break

        base_dupes = 1
        dupes = max(1, round(base_dupes * pack_def.dupe_boost_multiplier))

        results.append({
            "card_id": selected_card_id,
            "hero_id": hero_id,
            "duplicates": dupes,
            "is_joker": False,
        })

    return results


def process_premium_purchases(
    day: int,
    config: HeroCardConfig,
    game_state: HeroCardGameState,
    rng: Optional[Random] = None,
) -> Tuple[List[Dict[str, Any]], int, int]:
    """Process all premium pack purchases for a day.

    Returns: (all_pull_results, total_diamonds_spent, jokers_received)
    """
    # Check if there's a purchase schedule entry for this day
    day_index = (day - 1) % len(config.premium_pack_purchase_schedule) if config.premium_pack_purchase_schedule else -1
    if day_index < 0:
        return [], 0, 0

    purchases = config.premium_pack_purchase_schedule[day_index]
    available = get_available_packs(day, config.premium_pack_schedule, config.premium_packs)
    available_by_id = {p.pack_id: p for p in available}

    all_results: List[Dict[str, Any]] = []
    total_diamonds = 0
    total_jokers = 0

    for pack_id, count in purchases.items():
        pack_def = available_by_id.get(pack_id)
        if not pack_def or count <= 0:
            continue

        for _ in range(count):
            pulls = open_premium_pack(pack_def, game_state, rng)
            all_results.extend(pulls)
            total_diamonds += pack_def.diamond_cost
            total_jokers += sum(1 for p in pulls if p.get("is_joker", False))

    return all_results, total_diamonds, total_jokers
