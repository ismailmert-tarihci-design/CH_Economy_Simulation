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
    SharedUpgradeCostTable,
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

            # Grant Hero XP to shared pool
            game_state.shared_hero_xp += xp_reward
            total_xp += xp_reward

            # Check shared hero level up
            leveled_up = _check_shared_level_up(game_state, config)

            # Check skill tree advancement for ALL heroes on shared level-up
            if leveled_up:
                for check_hid, check_hstate in game_state.heroes.items():
                    check_hdef = _get_hero_def(config, check_hid)
                    if check_hdef:
                        activated = check_and_advance_skill_tree(
                            check_hdef, check_hstate, game_state.shared_hero_level
                        )
                        if activated:
                            tree_activations.setdefault(check_hid, []).extend(activated)

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


def _check_shared_level_up(
    game_state: HeroCardGameState,
    config: HeroCardConfig,
) -> bool:
    """Check if shared hero XP has reached the next level threshold. May level multiple times."""
    leveled = False
    while game_state.shared_hero_level < config.shared_max_hero_level:
        level_idx = game_state.shared_hero_level - 1
        if level_idx >= len(config.shared_xp_per_level):
            break
        threshold = config.shared_xp_per_level[level_idx]
        if game_state.shared_hero_xp >= threshold:
            game_state.shared_hero_xp -= threshold
            game_state.shared_hero_level += 1
            leveled = True
        else:
            break
    return leveled


# ---------------------------------------------------------------------------
# Shared card upgrades (no XP, no jokers)
# ---------------------------------------------------------------------------

def _get_shared_upgrade_table(
    config: HeroCardConfig, category: str
) -> Optional[SharedUpgradeCostTable]:
    for t in config.shared_upgrade_tables:
        if t.category == category:
            return t
    return None


def attempt_shared_upgrades(
    game_state: HeroCardGameState,
    config: HeroCardConfig,
) -> Tuple[List[Dict[str, Any]], int]:
    """Greedy upgrade loop for shared cards.

    Lowest level first. Consumes dupes + coins -> level up -> bluestars.
    No XP, no jokers.

    Returns: (upgrade_events, total_bluestars_earned)
    """
    events: List[Dict[str, Any]] = []
    total_bluestars = 0

    made_progress = True
    while made_progress:
        made_progress = False

        candidates = sorted(game_state.shared_cards, key=lambda c: c.level)
        for card in candidates:
            table = _get_shared_upgrade_table(config, card.category)
            if not table:
                continue

            level_idx = card.level - 1
            if level_idx >= len(table.duplicate_costs):
                continue
            if level_idx >= len(table.coin_costs):
                continue

            dupe_cost = table.duplicate_costs[level_idx]
            coin_cost = table.coin_costs[level_idx]
            bluestar_reward = table.bluestar_rewards[level_idx] if level_idx < len(table.bluestar_rewards) else 0

            if card.duplicates < dupe_cost:
                continue
            if game_state.coins < coin_cost:
                continue

            card.duplicates -= dupe_cost
            game_state.coins -= coin_cost
            old_level = card.level
            card.level += 1
            game_state.total_bluestars += bluestar_reward
            total_bluestars += bluestar_reward

            events.append({
                "card_id": card.id if hasattr(card, "id") else getattr(card, "card_id", "?"),
                "category": card.category,
                "old_level": old_level,
                "new_level": card.level,
                "dupes_spent": dupe_cost,
                "coins_spent": coin_cost,
                "bluestars_earned": bluestar_reward,
            })

            made_progress = True
            break  # Restart scan from lowest level

    return events, total_bluestars
