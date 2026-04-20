"""Per-hero card pool management.

Handles hero initialization, card unlocking via skill tree, and pool queries.
"""

from __future__ import annotations

from typing import Dict, List

from simulation.variants.variant_b.models import (
    HeroCardState,
    HeroDef,
    HeroProgressState,
)


def initialize_hero(hero_def: HeroDef) -> HeroProgressState:
    """Create initial runtime state for a hero at unlock time."""
    cards: Dict[str, HeroCardState] = {}
    for card_def in hero_def.card_pool:
        cards[card_def.card_id] = HeroCardState(
            card_id=card_def.card_id,
            hero_id=hero_def.hero_id,
            rarity=card_def.rarity,
            level=1,
            duplicates=0,
            unlocked=card_def.card_id in hero_def.starter_card_ids,
        )
    return HeroProgressState(
        hero_id=hero_def.hero_id,
        xp=0,
        level=1,
        skill_tree_progress=-1,
        cards=cards,
        joker_count=0,
    )


def get_unlocked_cards(hero_state: HeroProgressState) -> List[HeroCardState]:
    """Return all unlocked cards for a hero."""
    return [c for c in hero_state.cards.values() if c.unlocked]


def get_unlockable_cards_at_node(hero_def: HeroDef, node_index: int) -> List[str]:
    """Return card_ids that should be unlocked at a given skill tree node."""
    if node_index < 0 or node_index >= len(hero_def.skill_tree):
        return []
    return hero_def.skill_tree[node_index].cards_unlocked


def unlock_cards(hero_state: HeroProgressState, card_ids: List[str]) -> int:
    """Unlock cards by ID. Returns count of newly unlocked cards."""
    count = 0
    for card_id in card_ids:
        if card_id in hero_state.cards and not hero_state.cards[card_id].unlocked:
            hero_state.cards[card_id].unlocked = True
            count += 1
    return count


def hero_card_avg_level(hero_state: HeroProgressState) -> float:
    """Compute average level across all unlocked cards for a hero."""
    unlocked = get_unlocked_cards(hero_state)
    if not unlocked:
        return 0.0
    return sum(c.level for c in unlocked) / len(unlocked)
