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


def _randint_inclusive(lo: int, hi: int, rng: Optional[Random]) -> int:
    """Pick an int in [lo, hi]. Deterministic = midpoint when rng is None."""
    if hi < lo:
        hi = lo
    if rng:
        return rng.randint(lo, hi)
    return (lo + hi) // 2


def _draw_card_for_pack(
    pack_def: PremiumPackDef,
    pull_since_gold: int,
    got_gold: bool,
    dupe_min_pct: Dict[str, float],
    dupe_max_pct: Dict[str, float],
    pull_kind: str,
    game_state: HeroCardGameState,
    config: HeroCardConfig,
    rng: Optional[Random],
) -> Tuple[Optional[Dict[str, Any]], bool]:
    """Draw one card for a premium pack.

    Returns (result_dict or None if no card available, gold_was_pulled).
    pull_since_gold is 1-indexed (matches the PullSinceUniqueGold table).
    """
    # Determine rarity weights for this pull
    if got_gold:
        weights = pack_def.default_rarity_weights
    elif pack_def.pull_rarity_schedule:
        idx = max(0, min(pull_since_gold - 1, len(pack_def.pull_rarity_schedule) - 1))
        weights = pack_def.pull_rarity_schedule[idx]
    else:
        weights = pack_def.default_rarity_weights

    chosen_rarity = _roll_rarity(weights, rng)

    selected_card_id = _pick_card_by_rarity_catchup(
        chosen_rarity, pack_def.featured_hero_ids, game_state, rng
    )
    if not selected_card_id:
        for fallback in HeroCardRarity:
            if fallback != chosen_rarity:
                selected_card_id = _pick_card_by_rarity_catchup(
                    fallback, pack_def.featured_hero_ids, game_state, rng
                )
                if selected_card_id:
                    chosen_rarity = fallback
                    break
    if not selected_card_id:
        return None, False

    hero_id, card_level, card_rarity = _resolve_card_info(selected_card_id, game_state)
    if card_rarity is None:
        card_rarity = chosen_rarity

    # Compute duplicates as % of required dupes for next level, sampled from
    # [min_pct, max_pct] for this rarity.
    upgrade_table = _find_upgrade_table(config, card_rarity)
    level_idx = card_level - 1
    if upgrade_table and 0 <= level_idx < len(upgrade_table.duplicate_costs):
        base_cost = upgrade_table.duplicate_costs[level_idx]
        rarity_key = card_rarity.value
        min_pct = dupe_min_pct.get(rarity_key, 1.0)
        max_pct = dupe_max_pct.get(rarity_key, max(min_pct, 1.0))
        if max_pct < min_pct:
            max_pct = min_pct
        pct = rng.uniform(min_pct, max_pct) if rng else (min_pct + max_pct) / 2.0
        dupes = max(1, round(base_cost * pct))
    else:
        dupes = compute_hero_duplicates(card_level, card_rarity, config, rng) or 1

    return {
        "card_id": selected_card_id,
        "hero_id": hero_id,
        "duplicates": dupes,
        "is_joker": False,
        "rarity": card_rarity.value,
        "pull_kind": pull_kind,
    }, (card_rarity == HeroCardRarity.GOLD)


def open_premium_pack(
    pack_def: PremiumPackDef,
    game_state: HeroCardGameState,
    config: HeroCardConfig,
    rng: Optional[Random] = None,
) -> List[Dict[str, Any]]:
    """Open a Hero Unique Pack and return list of pull results.

    New structure:
      - N MainUpgradeCards (count rolled in [main_cards_min, main_cards_max], dupes per main_dupe_*_pct)
      - M BonusCards     (count rolled in [bonus_cards_min, bonus_cards_max], dupes per bonus_dupe_*_pct)
      - Optional jokers, coins, hero tokens (pack-level probability + min/max ranges)

    Rarity weights are indexed by PullSinceUniqueGold across both Main and Bonus
    pulls. After a gold is pulled, default_rarity_weights apply.
    """
    results: List[Dict[str, Any]] = []

    main_count = _randint_inclusive(pack_def.main_cards_min, pack_def.main_cards_max, rng)
    bonus_count = _randint_inclusive(pack_def.bonus_cards_min, pack_def.bonus_cards_max, rng)

    got_gold = False
    pull_since_gold = 1  # 1-indexed counter aligning with the spec's PullSinceUniqueGold

    # ---- MainUpgradeCards ----
    for _ in range(main_count):
        result, gold_pulled = _draw_card_for_pack(
            pack_def, pull_since_gold, got_gold,
            pack_def.main_dupe_min_pct, pack_def.main_dupe_max_pct,
            "main", game_state, config, rng,
        )
        if result is None:
            break
        results.append(result)
        if gold_pulled and not got_gold:
            got_gold = True
            pull_since_gold = 1
        else:
            pull_since_gold += 1

    # ---- BonusCards ----
    for _ in range(bonus_count):
        result, gold_pulled = _draw_card_for_pack(
            pack_def, pull_since_gold, got_gold,
            pack_def.bonus_dupe_min_pct, pack_def.bonus_dupe_max_pct,
            "bonus", game_state, config, rng,
        )
        if result is None:
            break
        results.append(result)
        if gold_pulled and not got_gold:
            got_gold = True
            pull_since_gold = 1
        else:
            pull_since_gold += 1

    # ---- HeroUniqueJoker (pack-level probability + count range) ----
    joker_roll = rng.random() if rng else 0.5
    if pack_def.joker_probability > 0 and joker_roll < pack_def.joker_probability:
        joker_count = _randint_inclusive(pack_def.joker_min, pack_def.joker_max, rng)
        if joker_count > 0:
            results.append({
                "card_id": "__joker__",
                "hero_id": pack_def.featured_hero_ids[0] if pack_def.featured_hero_ids else "",
                "duplicates": joker_count,
                "is_joker": True,
                "joker_count": joker_count,
            })

    # ---- Coins ----
    coins_roll = rng.random() if rng else 0.0
    if pack_def.coins_probability > 0 and coins_roll < pack_def.coins_probability:
        amount = _randint_inclusive(pack_def.coins_min, pack_def.coins_max, rng)
        if amount > 0:
            results.append({
                "card_id": "__reward_coins__",
                "hero_id": "",
                "duplicates": 0,
                "is_joker": False,
                "reward_type": "coins",
                "reward_amount": amount,
            })

    # ---- HeroTokens ----
    tokens_roll = rng.random() if rng else 0.0
    if pack_def.hero_tokens_probability > 0 and tokens_roll < pack_def.hero_tokens_probability:
        amount = _randint_inclusive(pack_def.hero_tokens_min, pack_def.hero_tokens_max, rng)
        if amount > 0:
            results.append({
                "card_id": "__hero_tokens__",
                "hero_id": pack_def.featured_hero_ids[0] if pack_def.featured_hero_ids else "",
                "duplicates": 0,
                "is_joker": False,
                "reward_type": "hero_tokens",
                "reward_amount": amount,
            })

    # ---- Legacy `additional_rewards` (still honored for back-compat) ----
    for reward in pack_def.additional_rewards:
        roll = rng.random() if rng else 0.5
        if roll < reward.probability:
            if reward.min_amount == reward.max_amount:
                amount = reward.min_amount
            elif rng:
                amount = rng.randint(reward.min_amount, reward.max_amount)
            else:
                amount = reward.min_amount
            results.append({
                "card_id": f"__reward_{reward.reward_type}__",
                "hero_id": "",
                "duplicates": 0,
                "is_joker": False,
                "reward_type": reward.reward_type,
                "reward_amount": amount,
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
) -> Tuple[List[Dict[str, Any]], int, int, int, int]:
    """Process all premium pack purchases for a day.

    Returns: (all_pull_results, total_diamonds_spent, jokers_received, hero_tokens_received, packs_opened)
    """
    day_index = (day - 1) % len(config.premium_pack_purchase_schedule) if config.premium_pack_purchase_schedule else -1
    if day_index < 0:
        return [], 0, 0, 0, 0

    purchases = config.premium_pack_purchase_schedule[day_index]
    available = get_available_packs(day, config.premium_pack_schedule, config.premium_packs)
    available_by_id = {p.pack_id: p for p in available}

    all_results: List[Dict[str, Any]] = []
    total_diamonds = 0
    total_jokers = 0
    total_hero_tokens = 0
    total_packs_opened = 0

    for pack_id, count in purchases.items():
        pack_def = available_by_id.get(pack_id)
        if not pack_def or count <= 0:
            continue

        for _ in range(count):
            pulls = open_premium_pack(pack_def, game_state, config, rng)
            all_results.extend(pulls)
            total_packs_opened += 1
            total_diamonds += pack_def.diamond_cost
            total_jokers += sum(1 for p in pulls if p.get("is_joker", False))
            total_hero_tokens += sum(
                p.get("reward_amount", 0) for p in pulls
                if p.get("reward_type") == "hero_tokens"
            )

    return all_results, total_diamonds, total_jokers, total_hero_tokens, total_packs_opened
