"""Upgrade engine for Variant B — Hero Card System.

Handles hero card upgrades (consuming dupes + coins, granting bluestars + Hero XP),
hero leveling (XP thresholds), and skill tree advancement.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from simulation.variants.variant_b.models import (
    HeroCardConfig,
    HeroCardGameState,
    HeroCardState,
    HeroDef,
    HeroProgressState,
    HeroUpgradeCostTable,
)
from simulation.variants.variant_b.hero_deck import get_unlocked_cards
from simulation.variants.variant_b.hero_joker import consume_joker, jokers_available
from simulation.variants.variant_b.skill_tree import check_and_advance_skill_tree


def _get_upgrade_table(
    config: HeroCardConfig, rarity_value: str
) -> Optional[HeroUpgradeCostTable]:
    """Find the upgrade cost table for a given rarity."""
    for table in config.hero_upgrade_tables:
        if table.rarity.value == rarity_value:
            return table
    return None


def _get_hero_def(config: HeroCardConfig, hero_id: str) -> Optional[HeroDef]:
    """Find a hero definition by ID."""
    for h in config.heroes:
        if h.hero_id == hero_id:
            return h
    return None


def attempt_hero_upgrades(
    game_state: HeroCardGameState,
    config: HeroCardConfig,
) -> Tuple[List[Dict[str, Any]], int, int, Dict[str, List]]:
    """Greedy upgrade loop for hero cards.

    Priority: Lowest level cards first, across all heroes.
    Uses jokers as wildcard duplicates when regular dupes are insufficient.

    Returns:
        (upgrade_events, total_xp_earned, total_bluestars_earned, skill_tree_activations)
        skill_tree_activations: {hero_id: [(node_index, card_ids, perk_label), ...]}
    """
    events: List[Dict[str, Any]] = []
    total_xp = 0
    total_bluestars = 0
    tree_activations: Dict[str, List] = {}

    made_progress = True
    while made_progress:
        made_progress = False

        # Collect all upgrade candidates across all heroes, sorted by level
        candidates: List[Tuple[str, HeroCardState, HeroUpgradeCostTable, HeroDef]] = []
        for hero_id, hero_state in game_state.heroes.items():
            hero_def = _get_hero_def(config, hero_id)
            if not hero_def:
                continue
            for card in get_unlocked_cards(hero_state):
                table = _get_upgrade_table(config, card.rarity.value)
                if not table:
                    continue
                candidates.append((hero_id, card, table, hero_def))

        candidates.sort(key=lambda x: x[1].level)

        for hero_id, card, table, hero_def in candidates:
            hero_state = game_state.heroes[hero_id]
            level_idx = card.level - 1

            # Check bounds
            if level_idx >= len(table.duplicate_costs):
                continue
            if level_idx >= len(table.coin_costs):
                continue

            dupe_cost = table.duplicate_costs[level_idx]
            coin_cost = table.coin_costs[level_idx]
            bluestar_reward = table.bluestar_rewards[level_idx] if level_idx < len(table.bluestar_rewards) else 0
            xp_reward = table.xp_rewards[level_idx] if level_idx < len(table.xp_rewards) else 0

            # Check resources
            available_dupes = card.duplicates
            joker_needed = max(0, dupe_cost - available_dupes)
            joker_available = jokers_available(hero_state)

            if available_dupes + joker_available < dupe_cost:
                continue
            if game_state.coins < coin_cost:
                continue

            # Execute upgrade
            dupes_from_card = min(dupe_cost, card.duplicates)
            card.duplicates -= dupes_from_card
            jokers_used = consume_joker(hero_state, dupe_cost - dupes_from_card)

            game_state.coins -= coin_cost
            old_level = card.level
            card.level += 1
            game_state.total_bluestars += bluestar_reward
            total_bluestars += bluestar_reward

            # Grant Hero XP
            hero_state.xp += xp_reward
            total_xp += xp_reward

            # Check hero level up
            leveled_up = _check_hero_level_up(hero_state, hero_def)

            # Check skill tree advancement
            if leveled_up:
                activated = check_and_advance_skill_tree(hero_def, hero_state)
                if activated:
                    tree_activations.setdefault(hero_id, []).extend(activated)

            events.append({
                "hero_id": hero_id,
                "card_id": card.card_id,
                "old_level": old_level,
                "new_level": card.level,
                "dupes_spent": dupes_from_card,
                "jokers_spent": jokers_used,
                "coins_spent": coin_cost,
                "bluestars_earned": bluestar_reward,
                "xp_earned": xp_reward,
                "hero_leveled_up": leveled_up,
            })

            made_progress = True
            break  # Restart scan from lowest level

    return events, total_xp, total_bluestars, tree_activations


def _check_hero_level_up(hero_state: HeroProgressState, hero_def: HeroDef) -> bool:
    """Check if hero has enough XP to level up. Returns True if leveled."""
    leveled = False
    while hero_state.level < hero_def.max_level:
        level_idx = hero_state.level - 1
        if level_idx >= len(hero_def.xp_per_level):
            break
        threshold = hero_def.xp_per_level[level_idx]
        if hero_state.xp >= threshold:
            hero_state.xp -= threshold
            hero_state.level += 1
            leveled = True
        else:
            break
    return leveled
