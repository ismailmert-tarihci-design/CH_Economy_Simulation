"""Linear skill tree progression.

When a hero levels up, check if new skill tree nodes are unlocked.
Each node can unlock new cards and/or grant perk markers.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from simulation.variants.variant_b.models import HeroDef, HeroProgressState
from simulation.variants.variant_b.hero_deck import unlock_cards


def check_and_advance_skill_tree(
    hero_def: HeroDef,
    hero_state: HeroProgressState,
    shared_level: Optional[int] = None,
) -> List[Tuple[int, List[str], str]]:
    """Advance the skill tree based on shared hero level (or per-hero if not provided).

    Returns list of (node_index, newly_unlocked_card_ids, perk_label) for each
    node that was activated this call.
    """
    effective_level = shared_level if shared_level is not None else hero_state.level
    activated: List[Tuple[int, List[str], str]] = []

    for node in hero_def.skill_tree:
        if node.node_index <= hero_state.skill_tree_progress:
            continue  # Already unlocked
        if effective_level < node.hero_level_required:
            break  # Linear tree — stop at first unmet requirement

        hero_state.skill_tree_progress = node.node_index
        newly_unlocked = unlock_cards(hero_state, node.cards_unlocked)
        activated.append((
            node.node_index,
            node.cards_unlocked[:newly_unlocked] if newly_unlocked else [],
            node.perk_label,
        ))

    return activated
