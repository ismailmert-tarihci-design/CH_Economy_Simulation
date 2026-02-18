"""
Upgrade engine for the Bluestar Economy Simulator.

Implements greedy auto-upgrade strategy with priority ordering and resource checks.
"""

from dataclasses import dataclass

from simulation.coin_economy import CoinLedger
from simulation.models import Card, CardCategory, GameState, SimConfig, UpgradeTable
from simulation.progression import can_upgrade_unique, compute_category_progression


@dataclass
class UpgradeEvent:
    """Record of a single upgrade execution."""

    card_id: str
    old_level: int
    new_level: int
    dupes_spent: int
    coins_spent: int
    bluestars_earned: int
    day: int


def attempt_upgrades(
    game_state: GameState, config: SimConfig, coin_ledger: CoinLedger
) -> list[UpgradeEvent]:
    """
    Greedy auto-upgrade loop with priority: Unique > Gold > Blue.

    Within each category, upgrade lowest level first (catch-up).
    Loop until no more upgrades possible.

    Args:
        game_state: Current game state with cards and bluestars
        config: Simulation configuration with upgrade tables
        coin_ledger: Coin ledger for balance tracking

    Returns:
        List of UpgradeEvent records for all upgrades executed
    """
    events = []

    while True:
        # Get candidates in priority order
        candidates = get_upgrade_candidates(game_state, config)

        upgraded = False
        for card in candidates:
            if _can_upgrade(card, game_state, config, coin_ledger):
                event = _execute_upgrade(card, game_state, config, coin_ledger)
                events.append(event)
                upgraded = True
                break  # Restart candidate scan after upgrade

        if not upgraded:
            break  # No more upgrades possible

    return events


def get_upgrade_candidates(game_state: GameState, config: SimConfig) -> list[Card]:
    """
    Returns cards sorted by upgrade priority.

    Priority order:
    1. All UNIQUE cards (sorted by level ascending)
    2. All GOLD_SHARED cards (sorted by level ascending)
    3. All BLUE_SHARED cards (sorted by level ascending)

    Args:
        game_state: Current game state
        config: Simulation configuration

    Returns:
        List of cards in priority order
    """
    unique_cards = [c for c in game_state.cards if c.category == CardCategory.UNIQUE]
    gold_cards = [c for c in game_state.cards if c.category == CardCategory.GOLD_SHARED]
    blue_cards = [c for c in game_state.cards if c.category == CardCategory.BLUE_SHARED]

    # Sort each category by level ascending (catch-up: lowest first)
    unique_cards.sort(key=lambda c: c.level)
    gold_cards.sort(key=lambda c: c.level)
    blue_cards.sort(key=lambda c: c.level)

    # Concatenate in priority order
    return unique_cards + gold_cards + blue_cards


def _can_upgrade(
    card: Card, game_state: GameState, config: SimConfig, coin_ledger: CoinLedger
) -> bool:
    """
    Check ALL 4 conditions for upgrade eligibility.

    Conditions:
    1. Not at max level (100 for shared, 10 for unique)
    2. Sufficient duplicates
    3. Sufficient coins
    4. Gating check (unique only)

    Args:
        card: Card to check
        game_state: Current game state
        config: Simulation configuration
        coin_ledger: Coin ledger for balance checking

    Returns:
        True if all conditions pass, False otherwise
    """
    # Max level check
    max_level = (
        config.max_unique_level
        if card.category == CardCategory.UNIQUE
        else config.max_shared_level
    )
    if card.level >= max_level:
        return False

    # Get upgrade costs for current level → next level
    upgrade_table = config.upgrade_tables[card.category]
    dupe_cost = upgrade_table.duplicate_costs[card.level - 1]
    coin_cost = upgrade_table.coin_costs[card.level - 1]

    # Duplicate check
    if card.duplicates < dupe_cost:
        return False

    # Coin check
    if coin_ledger.balance < coin_cost:
        return False

    # Gating check (unique only)
    if card.category == CardCategory.UNIQUE:
        # Compute average shared progression
        gold_prog = compute_category_progression(
            game_state.cards, CardCategory.GOLD_SHARED, config.progression_mapping
        )
        blue_prog = compute_category_progression(
            game_state.cards, CardCategory.BLUE_SHARED, config.progression_mapping
        )
        avg_shared = (gold_prog + blue_prog) / 2.0

        # Convert to average shared level (0.0-1.0 → 0-100)
        avg_shared_level = avg_shared * 100.0

        if not can_upgrade_unique(card, avg_shared_level, config.progression_mapping):
            return False

    return True


def _execute_upgrade(
    card: Card, game_state: GameState, config: SimConfig, coin_ledger: CoinLedger
) -> UpgradeEvent:
    """
    Execute upgrade: deduct resources, increment level, award Bluestars.

    Args:
        card: Card to upgrade
        game_state: Current game state (modified in place)
        config: Simulation configuration
        coin_ledger: Coin ledger (modified in place)

    Returns:
        UpgradeEvent recording the upgrade details
    """
    old_level = card.level
    upgrade_table = config.upgrade_tables[card.category]

    # Get costs for current level (0-indexed)
    dupe_cost = upgrade_table.duplicate_costs[card.level - 1]
    coin_cost = upgrade_table.coin_costs[card.level - 1]

    # Get reward for this upgrade step (same indexing as costs)
    bluestar_reward = upgrade_table.bluestar_rewards[card.level - 1]

    # Deduct resources
    card.duplicates -= dupe_cost
    success = coin_ledger.spend(coin_cost, card.id, game_state.day)
    assert success, "Coin spend should succeed after can_afford check"

    # Increment level
    card.level += 1

    # Award Bluestars
    game_state.total_bluestars += bluestar_reward

    return UpgradeEvent(
        card_id=card.id,
        old_level=old_level,
        new_level=card.level,
        dupes_spent=dupe_cost,
        coins_spent=coin_cost,
        bluestars_earned=bluestar_reward,
        day=game_state.day,
    )
