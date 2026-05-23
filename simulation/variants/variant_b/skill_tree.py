"""Linear skill tree progression.

When a hero levels up, check if new skill tree nodes are unlocked.
Each node can unlock new cards and/or grant perk markers, and (optionally)
charges Hero Tokens from the supplied bonus-items wallet.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from simulation.variants.variant_b.models import HeroDef, HeroProgressState
from simulation.variants.variant_b.hero_deck import unlock_cards


_HERO_TOKENS_KEY = "HeroTokens"


def check_and_advance_skill_tree(
    hero_def: HeroDef,
    hero_state: HeroProgressState,
    shared_level: Optional[int] = None,
    bonus_items: Optional[Dict[str, int]] = None,
) -> List[Tuple[int, List[str], str]]:
    """Advance the skill tree based on hero level + (optionally) Hero Token balance.

    When `bonus_items` is provided, a node is only activated when the player
    can pay its `token_cost` — and the cost is debited from
    `bonus_items["HeroTokens"]`. When `bonus_items` is None, only the level
    gate is enforced (legacy behavior, used in tests/FTUE-style flows).

    Returns list of (node_index, newly_unlocked_card_ids, perk_label) for each
    node that was activated this call. Stops at the first node the player
    cannot afford or has not reached the level for (linear tree).
    """
    effective_level = shared_level if shared_level is not None else hero_state.level
    activated: List[Tuple[int, List[str], str]] = []

    for node in hero_def.skill_tree:
        if node.node_index <= hero_state.skill_tree_progress:
            continue  # Already unlocked
        if effective_level < node.hero_level_required:
            break  # Linear tree — stop at first unmet level requirement

        cost = max(0, int(getattr(node, "token_cost", 0) or 0))
        if bonus_items is not None and cost > 0:
            available = int(bonus_items.get(_HERO_TOKENS_KEY, 0))
            if available < cost:
                break  # Can't afford — stop (linear tree)
            bonus_items[_HERO_TOKENS_KEY] = available - cost

        hero_state.skill_tree_progress = node.node_index
        unlock_cards(hero_state, node.cards_unlocked)
        activated.append((
            node.node_index,
            node.cards_unlocked,
            node.perk_label,
        ))

    return activated
