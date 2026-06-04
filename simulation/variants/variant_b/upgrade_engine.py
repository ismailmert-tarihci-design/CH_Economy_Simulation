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


def try_upgrade_hero_card(
    game_state: HeroCardGameState,
    config: HeroCardConfig,
    hero_id: str,
    card_id: str,
) -> Optional[Tuple[Dict[str, Any], List]]:
    """Attempt a single hero-card upgrade.

    Returns (event_dict, tree_activations_list) on success, or None if the card
    cannot be upgraded (locked, missing, insufficient dupes+jokers, insufficient coins,
    or at max level for the table).

    Mutates game_state in place. Used both interactively (single button click) and
    by the greedy attempt_hero_upgrades loop.
    """
    hero_state = game_state.heroes.get(hero_id)
    if not hero_state:
        return None
    card = hero_state.cards.get(card_id)
    if not card or not card.unlocked:
        return None
    hero_def = _get_hero_def(config, hero_id)
    if not hero_def:
        return None
    table = _get_upgrade_table(config, card.rarity.value)
    if not table:
        return None

    level_idx = card.level - 1
    if level_idx >= len(table.duplicate_costs) or level_idx >= len(table.coin_costs):
        return None

    dupe_cost = table.duplicate_costs[level_idx]
    coin_cost = table.coin_costs[level_idx]
    bluestar_reward = table.bluestar_rewards[level_idx] if level_idx < len(table.bluestar_rewards) else 0
    xp_reward = table.xp_rewards[level_idx] if level_idx < len(table.xp_rewards) else 0

    available_dupes = card.duplicates
    joker_available = jokers_available(hero_state)
    if available_dupes + joker_available < dupe_cost:
        return None
    # Coins are no longer a gate — duplicates alone decide whether a card can
    # upgrade. The coin cost is still deducted/tracked, it just can't block.

    dupes_from_card = min(dupe_cost, card.duplicates)
    card.duplicates -= dupes_from_card
    jokers_used = consume_joker(hero_state, dupe_cost - dupes_from_card)

    game_state.coins -= coin_cost
    old_level = card.level
    card.level += 1
    game_state.total_bluestars += bluestar_reward
    hero_state.xp += xp_reward

    leveled_up = _check_hero_level_up(hero_state, hero_def)
    tree_activations: List = []
    if leveled_up:
        # `unlimited_hero_tokens` mode skips the affordability gate so nodes
        # activate purely on the hero-level requirement — this is how we measure
        # pure Hero Token demand independent of token income.
        wallet = None if getattr(config, "unlimited_hero_tokens", False) else game_state.bonus_items
        activated = check_and_advance_skill_tree(
            hero_def, hero_state, hero_state.level,
            bonus_items=wallet,
        )
        if activated:
            tree_activations.extend(activated)

    event = {
        "hero_id": hero_id,
        "card_id": card.card_id,
        "rarity": card.rarity.value if hasattr(card.rarity, "value") else str(card.rarity),
        "old_level": old_level,
        "new_level": card.level,
        "dupes_spent": dupes_from_card,
        "jokers_spent": jokers_used,
        "coins_spent": coin_cost,
        "bluestars_earned": bluestar_reward,
        "xp_earned": xp_reward,
        "hero_leveled_up": leveled_up,
    }
    return event, tree_activations


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

        candidates: List[Tuple[str, HeroCardState]] = []
        for hero_id, hero_state in game_state.heroes.items():
            for card in get_unlocked_cards(hero_state):
                candidates.append((hero_id, card))

        candidates.sort(key=lambda x: x[1].level)

        for hero_id, card in candidates:
            result = try_upgrade_hero_card(game_state, config, hero_id, card.card_id)
            if result is None:
                continue
            event, tree_acts = result
            events.append(event)
            total_xp += event["xp_earned"]
            total_bluestars += event["bluestars_earned"]
            if tree_acts:
                tree_activations.setdefault(hero_id, []).extend(tree_acts)
            made_progress = True
            break  # Restart scan from lowest level

    return events, total_xp, total_bluestars, tree_activations


def _check_hero_level_up(
    hero_state: HeroProgressState,
    hero_def: HeroDef,
) -> bool:
    """Check if a hero's XP has reached the next level threshold. May level multiple times."""
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


def try_upgrade_shared_card(
    game_state: HeroCardGameState,
    config: HeroCardConfig,
    card_id: str,
) -> Optional[Dict[str, Any]]:
    """Attempt a single shared-card upgrade. Returns event dict on success, None otherwise."""
    card = None
    for c in game_state.shared_cards:
        cid = getattr(c, "id", None) or getattr(c, "card_id", None)
        if cid == card_id:
            card = c
            break
    if card is None:
        return None

    category_value = card.category.value if hasattr(card.category, "value") else str(card.category)
    table = _get_shared_upgrade_table(config, category_value)
    if not table:
        return None

    level_idx = card.level - 1
    if level_idx >= len(table.duplicate_costs) or level_idx >= len(table.coin_costs):
        return None

    dupe_cost = table.duplicate_costs[level_idx]
    coin_cost = table.coin_costs[level_idx]
    bluestar_reward = table.bluestar_rewards[level_idx] if level_idx < len(table.bluestar_rewards) else 0

    if card.duplicates < dupe_cost:
        return None
    # Coins no longer gate shared-card upgrades (still deducted/tracked).

    card.duplicates -= dupe_cost
    game_state.coins -= coin_cost
    old_level = card.level
    card.level += 1
    game_state.total_bluestars += bluestar_reward

    return {
        "card_id": card_id,
        "category": category_value,
        "old_level": old_level,
        "new_level": card.level,
        "dupes_spent": dupe_cost,
        "coins_spent": coin_cost,
        "bluestars_earned": bluestar_reward,
    }


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
            cid = getattr(card, "id", None) or getattr(card, "card_id", None)
            if cid is None:
                continue
            event = try_upgrade_shared_card(game_state, config, cid)
            if event is None:
                continue
            events.append(event)
            total_bluestars += event["bluestars_earned"]
            made_progress = True
            break  # Restart scan from lowest level

    return events, total_bluestars
