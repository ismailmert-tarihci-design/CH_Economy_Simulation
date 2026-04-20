"""Hero-specific premium card pack economics.

Premium packs are diamond-only, rotating availability, FOMO-driven.
Each pack uses per-pull rarity weights that change until a gold is pulled.
Dupes use the same %-of-cost mechanic as regular pulls, with optional overrides.
"""

from __future__ import annotations

from random import Random
from typing import Any, Dict, List, Optional, Tuple

from simulation.variants.variant_b.models import (
    HeroCardConfig,
    HeroCardGameState,
    HeroCardRarity,
    HeroCardState,
    PremiumPackDef,
    PremiumPackPullRarity,
    PremiumPackSchedule,
)
from simulation.variants.variant_b.drop_algorithm import (
    _find_upgrade_table,
    compute_hero_duplicates,
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


def _roll_rarity(
    weights: PremiumPackPullRarity,
    rng: Optional[Random] = None,
) -> HeroCardRarity:
    """Roll a rarity from weighted probabilities."""
    items = [HeroCardRarity.GRAY, HeroCardRarity.BLUE, HeroCardRarity.GOLD]
    w = [weights.gray_weight, weights.blue_weight, weights.gold_weight]
    total = sum(w)
    if total <= 0:
        return HeroCardRarity.GRAY

    if rng:
        roll = rng.random() * total
        cumulative = 0.0
        for item, weight in zip(items, w):
            cumulative += weight
            if roll <= cumulative:
                return item
        return items[-1]
    else:
        best_idx = max(range(len(w)), key=lambda i: w[i])
        return items[best_idx]


def _pick_card_by_rarity_catchup(
    rarity: HeroCardRarity,
    hero_ids: List[str],
    game_state: HeroCardGameState,
    rng: Optional[Random] = None,
) -> Optional[str]:
    """Pick a card of the given rarity from featured heroes' unlocked cards.

    Uses lowest-level-first catch-up weighting: weight = 1/(level+1).
    """
    candidates: List[HeroCardState] = []
    for hid in hero_ids:
        hstate = game_state.heroes.get(hid)
        if not hstate:
            continue
        for card in hstate.cards.values():
            if card.unlocked and card.rarity == rarity:
                candidates.append(card)

    if not candidates:
        return None

    weights = [1.0 / (c.level + 1) for c in candidates]
    total = sum(weights)
    if total <= 0:
        return candidates[0].card_id

    if rng:
        roll = rng.random() * total
        cumulative = 0.0
        for card, w in zip(candidates, weights):
            cumulative += w
            if roll <= cumulative:
                return card.card_id
        return candidates[-1].card_id
    else:
        best_idx = max(range(len(weights)), key=lambda i: weights[i])
        return candidates[best_idx].card_id


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
    - Per-pull rarity weights that change until gold is pulled
    - Gold guarantee: at least one GOLD rarity card per pack
    - Dupe override per rarity
    - Hero tokens gifted per pack
    - Additional probability-based rewards
    """
    results: List[Dict[str, Any]] = []

    # Determine card count for this pack
    if rng:
        num_cards = rng.randint(pack_def.min_cards_per_pack, pack_def.max_cards_per_pack)
    else:
        num_cards = (pack_def.min_cards_per_pack + pack_def.max_cards_per_pack) // 2

    got_gold = False

    for draw_idx in range(num_cards):
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

        # Determine rarity for this pull
        if pack_def.pull_rarity_schedule:
            # Gold guarantee: force gold on last card if none yet
            if pack_def.gold_guarantee and draw_idx == num_cards - 1 and not got_gold:
                chosen_rarity = HeroCardRarity.GOLD
            elif got_gold:
                chosen_rarity = _roll_rarity(pack_def.default_rarity_weights, rng)
            elif draw_idx < len(pack_def.pull_rarity_schedule):
                chosen_rarity = _roll_rarity(pack_def.pull_rarity_schedule[draw_idx], rng)
            else:
                chosen_rarity = _roll_rarity(pack_def.default_rarity_weights, rng)

            if chosen_rarity == HeroCardRarity.GOLD:
                got_gold = True

            # Pick card of chosen rarity using catch-up
            selected_card_id = _pick_card_by_rarity_catchup(
                chosen_rarity, pack_def.featured_hero_ids, game_state, rng
            )
        else:
            # Legacy: fall back to card_drop_rates
            card_rates = [(cr.card_id, cr.drop_rate) for cr in pack_def.card_drop_rates]
            total_weight = sum(r for _, r in card_rates)
            selected_card_id = _pick_card_weighted(card_rates, total_weight, rng)

        if not selected_card_id:
            continue

        hero_id, card_level, card_rarity = _resolve_card_info(selected_card_id, game_state)

        if card_rarity == HeroCardRarity.GOLD:
            got_gold = True

        # Compute duplicates (with optional % override)
        if card_rarity is not None:
            pct_override = pack_def.dupe_pct_per_rarity.get(card_rarity.value, 0.0)
            if pct_override > 0:
                # % of required dupes for next level
                upgrade_table = _find_upgrade_table(config, card_rarity)
                level_idx = card_level - 1
                if upgrade_table and level_idx < len(upgrade_table.duplicate_costs):
                    base_cost = upgrade_table.duplicate_costs[level_idx]
                    dupes = max(1, round(base_cost * pct_override))
                else:
                    dupes = 1
            else:
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


def _pick_card_weighted(
    card_rates: List[Tuple[str, float]],
    total_weight: float,
    rng: Optional[Random] = None,
) -> Optional[str]:
    """Legacy: Pick a card_id via weighted random selection."""
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
