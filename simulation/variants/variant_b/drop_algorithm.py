"""Drop algorithm for Variant B — Hero Card System.

Decides: shared card (Gold/Blue) or hero card?
Then selects which card, and computes duplicates.
"""

from __future__ import annotations

import hashlib
from random import Random
from typing import Any, Dict, List, Optional, Tuple

from simulation.variants.variant_b.models import (
    HeroCardConfig,
    HeroCardGameState,
    HeroCardState,
    HeroProgressState,
)
from simulation.variants.variant_b.hero_deck import get_unlocked_cards


def decide_hero_or_shared(
    game_state: HeroCardGameState,
    config: HeroCardConfig,
    rng: Optional[Random] = None,
) -> str:
    """Decide whether the next pull is a hero card or a shared card.

    Returns: "hero" or "shared"
    """
    dc = config.drop_config
    base_hero = dc.hero_vs_shared_base_rate
    base_shared = 1.0 - base_hero

    # Pity system: guarantee hero card after N shared-only pulls
    if dc.pity_counter_threshold > 0 and game_state.pity_counter >= dc.pity_counter_threshold:
        return "hero"

    if rng:
        roll = rng.random()
    else:
        # Deterministic: hash-based
        h = hashlib.md5(f"hero_or_shared_{game_state.day}_{game_state.pity_counter}".encode())
        roll = int(h.hexdigest()[:8], 16) / 0xFFFFFFFF

    return "hero" if roll < base_hero else "shared"


def select_hero_card(
    game_state: HeroCardGameState,
    config: HeroCardConfig,
    rng: Optional[Random] = None,
) -> Optional[Tuple[str, str]]:
    """Select which hero's card to drop.

    Returns: (hero_id, card_id) or None if no hero cards available.
    """
    # Collect all unlocked cards across all heroes
    candidates: List[Tuple[str, HeroCardState]] = []
    for hero_id, hero_state in game_state.heroes.items():
        for card in get_unlocked_cards(hero_state):
            candidates.append((hero_id, card))

    if not candidates:
        return None

    mode = config.drop_config.card_selection_mode

    if mode == "lowest_level":
        # Favor lowest-level cards (catch-up mechanic)
        candidates.sort(key=lambda x: x[1].level)
        weights = [1.0 / (c[1].level + 1) for c in candidates]
    elif mode == "weighted_rarity":
        # Rarer cards have lower weight (more common cards drop more)
        rarity_weights = {"COMMON": 5.0, "UNCOMMON": 3.0, "RARE": 2.0, "EPIC": 1.0, "LEGENDARY": 0.5}
        weights = [rarity_weights.get(c[1].rarity.value, 1.0) for c in candidates]
    else:
        # Equal weight
        weights = [1.0] * len(candidates)

    total = sum(weights)
    if total <= 0:
        return None

    if rng:
        roll = rng.random() * total
        cumulative = 0.0
        for (hero_id, card), w in zip(candidates, weights):
            cumulative += w
            if roll <= cumulative:
                return hero_id, card.card_id
        return candidates[-1][0], candidates[-1][1].card_id
    else:
        # Deterministic: pick highest weight
        best_idx = max(range(len(weights)), key=lambda i: weights[i])
        return candidates[best_idx][0], candidates[best_idx][1].card_id


def select_shared_card(
    game_state: HeroCardGameState,
    rng: Optional[Random] = None,
) -> Optional[Any]:
    """Select a shared card (Gold/Blue) using lowest-level-first.

    Returns the Card object or None.
    """
    if not game_state.shared_cards:
        return None

    # Sort by level ascending
    sorted_cards = sorted(game_state.shared_cards, key=lambda c: c.level)
    weights = [1.0 / (c.level + 1) for c in sorted_cards]
    total = sum(weights)

    if rng and total > 0:
        roll = rng.random() * total
        cumulative = 0.0
        for card, w in zip(sorted_cards, weights):
            cumulative += w
            if roll <= cumulative:
                return card
        return sorted_cards[-1]
    else:
        return sorted_cards[0]


def compute_hero_duplicates(
    card_level: int,
    rng: Optional[Random] = None,
) -> int:
    """Compute duplicates received for a hero card pull.

    Simple model: 1-3 dupes, slightly more at lower levels.
    """
    base = max(1, 4 - card_level // 10)
    if rng:
        return max(1, rng.randint(1, base))
    return max(1, (1 + base) // 2)


def check_joker_drop(
    config: HeroCardConfig,
    rng: Optional[Random] = None,
) -> bool:
    """Check if a hero joker drops in a regular pack pull."""
    rate = config.joker_drop_rate_in_regular_packs
    if rng:
        return rng.random() < rate
    return rate > 0.5
