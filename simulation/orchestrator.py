"""
Simulation orchestrator for the Bluestar Economy Simulator.

Main integration module that orchestrates the daily loop:
1. Check unique unlock schedule
2. Process packs for the day
3. For each card pull: perform pull, then attempt upgrades immediately
4. Record daily snapshot
"""

from dataclasses import dataclass
from random import Random
from typing import Any, Dict, List, Optional

from simulation.coin_economy import CoinLedger
from simulation.drop_algorithm import perform_card_pull
from simulation.models import (
    Card,
    CardCategory,
    GameState,
    SimConfig,
    SimResult,
    StreakState,
)
from simulation.pack_system import process_packs_for_day
from simulation.progression import get_unlocked_unique_count
from simulation.pull_logger import PullLogger
from simulation.upgrade_engine import UpgradeEvent, attempt_upgrades


@dataclass
class DailySnapshot:
    """Records the state of the game for a single day."""

    day: int
    total_bluestars: int
    bluestars_earned_today: int
    coins_balance: int
    coins_earned_today: int
    coins_spent_today: int
    card_levels: Dict[str, int]
    upgrades_today: List[UpgradeEvent]
    category_avg_levels: Dict[str, float]
    total_unique_unlocked: int


def create_initial_state(
    config: SimConfig,
) -> tuple[GameState, CoinLedger, StreakState]:
    """
    Create initial game state for simulation.

    Sets up:
    - Gold Shared cards (count from config.num_gold_cards)
    - Blue Shared cards (count from config.num_blue_cards)
    - Initial unique cards based on day 1 unlock schedule

    Args:
        config: Simulation configuration

    Returns:
        Tuple of (game_state, coin_ledger, streak_state)
    """
    cards = []

    # Gold Shared cards (configurable count)
    for i in range(1, config.num_gold_cards + 1):
        cards.append(
            Card(
                id=f"gold_{i}",
                name=f"Gold Shared {i}",
                category=CardCategory.GOLD_SHARED,
                level=1,
                duplicates=0,
            )
        )

    # Blue Shared cards (configurable count)
    for i in range(1, config.num_blue_cards + 1):
        cards.append(
            Card(
                id=f"blue_{i}",
                name=f"Blue Shared {i}",
                category=CardCategory.BLUE_SHARED,
                level=1,
                duplicates=0,
            )
        )

    # Initial unique cards from day 1 unlock schedule
    initial_unique_count = get_unlocked_unique_count(1, config.unique_unlock_schedule)
    for i in range(1, initial_unique_count + 1):
        cards.append(
            Card(
                id=f"hero_{i}",
                name=f"Hero {i}",
                category=CardCategory.UNIQUE,
                level=1,
                duplicates=0,
            )
        )

    game_state = GameState(
        day=0,
        cards=cards,
        coins=config.initial_coins,
        total_bluestars=config.initial_bluestars,
        streak_state=StreakState(
            streak_shared=0,
            streak_unique=0,
            streak_per_color={},
            streak_per_hero={},
        ),
    )

    coin_ledger = CoinLedger(balance=config.initial_coins)

    streak_state = StreakState(
        streak_shared=0,
        streak_unique=0,
        streak_per_color={},
        streak_per_hero={},
    )

    return game_state, coin_ledger, streak_state


def _get_day_pack_counts(config: SimConfig, day: int) -> dict[str, float]:
    schedule = config.daily_pack_schedule
    if not schedule:
        return {}
    # day is 1-indexed; schedule is 0-indexed; loop using modulo
    index = (day - 1) % len(schedule)
    return schedule[index]


def run_simulation(config: SimConfig, rng: Optional[Random] = None) -> SimResult:
    """
    Main deterministic simulation loop.

    Daily loop order (CRITICAL):
    1. Check unique unlock schedule
    2. Process packs for day
    3. For each card pull (sequential with streak propagation):
       a. Perform card pull
       b. Attempt upgrades immediately (greedy loop)
    4. Record daily snapshot

    Args:
        config: Simulation configuration
        rng: Random instance for Monte Carlo mode (None = deterministic)

    Returns:
        SimResult with daily snapshots and aggregate statistics
    """
    game_state, coin_ledger, streak_state = create_initial_state(config)
    daily_snapshots: List[DailySnapshot] = []
    pull_logger = PullLogger()

    for day in range(1, config.num_days + 1):
        game_state.day = day

        # Step a: Check unique unlock schedule
        unlocked_count = get_unlocked_unique_count(day, config.unique_unlock_schedule)
        current_unique_count = len(
            [c for c in game_state.cards if c.category == CardCategory.UNIQUE]
        )

        # Add new unique cards if schedule unlocked more
        if unlocked_count > current_unique_count:
            for i in range(current_unique_count + 1, unlocked_count + 1):
                game_state.cards.append(
                    Card(
                        id=f"hero_{i}",
                        name=f"Hero {i}",
                        category=CardCategory.UNIQUE,
                        level=1,
                        duplicates=0,
                    )
                )

        # Step b: Process packs
        day_pack_counts = _get_day_pack_counts(config, day)
        card_pulls = process_packs_for_day(game_state, config, rng, day_pack_counts)

        # Step c: For each CardPull (SEQUENTIAL - ORDER MATTERS)
        # After each pull, attempt upgrades immediately (a typical player
        # would try upgrades after every pull, not wait until end of day).
        upgrade_events: List[UpgradeEvent] = []
        pull_index = 0
        for _card_pull in card_pulls:
            pull_index += 1
            card, dupes, coins, updated_streak = perform_card_pull(
                game_state, config, streak_state, rng
            )
            level_before = card.level
            card.duplicates += dupes
            coin_ledger.add_income(coins, card.id, day)
            streak_state = updated_streak  # CRITICAL: propagate streak state

            pull_upgrades = attempt_upgrades(game_state, config, coin_ledger)
            upgrade_events.extend(pull_upgrades)

            pull_logger.log_pull(
                day=day,
                pull_index=pull_index,
                card_id=card.id,
                card_name=card.name,
                card_category=card.category.value,
                card_level_before=level_before,
                duplicates_received=dupes,
                duplicates_total_after=card.duplicates,
                coins_earned=coins,
                upgrades=pull_upgrades,
            )

        # Step e: Record DailySnapshot
        summary = coin_ledger.daily_summary(day)
        coins_earned_today = summary["total_income"]
        coins_spent_today = summary["total_spent"]

        bluestars_earned_today = sum(e.bluestars_earned for e in upgrade_events)

        # Calculate category average levels
        category_avg_levels = {}
        for category in [
            CardCategory.GOLD_SHARED,
            CardCategory.BLUE_SHARED,
            CardCategory.UNIQUE,
        ]:
            cat_cards = [c for c in game_state.cards if c.category == category]
            if cat_cards:
                category_avg_levels[category.value] = sum(
                    c.level for c in cat_cards
                ) / len(cat_cards)
            else:
                category_avg_levels[category.value] = 0.0

        snapshot = DailySnapshot(
            day=day,
            total_bluestars=game_state.total_bluestars,
            bluestars_earned_today=bluestars_earned_today,
            coins_balance=coin_ledger.balance,
            coins_earned_today=coins_earned_today,
            coins_spent_today=coins_spent_today,
            card_levels={card.id: card.level for card in game_state.cards},
            upgrades_today=upgrade_events,
            category_avg_levels=category_avg_levels,
            total_unique_unlocked=unlocked_count,
        )
        daily_snapshots.append(snapshot)

    # Compute aggregate statistics
    total_coins_earned = sum(
        t.amount for t in coin_ledger.transactions if t.source == "income"
    )
    total_coins_spent = sum(
        t.amount for t in coin_ledger.transactions if t.source == "spend"
    )

    total_upgrades: Dict[str, Any] = {}
    for snapshot in daily_snapshots:
        for event in snapshot.upgrades_today:
            if event.card_id not in total_upgrades:
                total_upgrades[event.card_id] = 0
            total_upgrades[event.card_id] += 1

    return SimResult(
        daily_snapshots=daily_snapshots,
        total_bluestars=game_state.total_bluestars,
        total_coins_earned=total_coins_earned,
        total_coins_spent=total_coins_spent,
        total_upgrades=total_upgrades,
        pull_logs=pull_logger.events,
    )
