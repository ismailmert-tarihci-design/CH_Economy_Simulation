"""Linear skill tree progression.

When a hero levels up, check if new skill tree nodes are unlocked.
Each node can unlock new cards and/or grant perk markers.
"""

from __future__ import annotations

from typing import List, Tuple

from simulation.variants.variant_b.models import HeroDef, HeroProgressState
from simulation.variants.variant_b.hero_deck import unlock_cards


def check_and_advance_skill_tree(
    hero_def: HeroDef,
    hero_state: HeroProgressState,
) -> List[Tuple[int, List[str], str]]:
    """Advance the skill tree based on current hero level.

    Returns list of (node_index, newly_unlocked_card_ids, perk_label) for each
    node that was activated this call.
    """
    activated: List[Tuple[int, List[str], str]] = []

    for node in hero_def.skill_tree:
        if node.node_index <= hero_state.skill_tree_progress:
            continue  # Already unlocked
        if hero_state.level < node.hero_level_required:
            break  # Linear tree — stop at first unmet requirement

        hero_state.skill_tree_progress = node.node_index
        newly_unlocked = unlock_cards(hero_state, node.cards_unlocked)
        activated.append((
            node.node_index,
            node.cards_unlocked[:newly_unlocked] if newly_unlocked else [],
            node.perk_label,
        ))

    return activated
