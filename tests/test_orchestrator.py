"""
Tests for the simulation orchestrator module.

Covers initialization, daily loop integration, snapshot recording, and performance.
"""

import time

import pytest

from simulation.models import (
    CardCategory,
    CardTypesRange,
    CoinPerDuplicate,
    DuplicateRange,
    PackConfig,
    ProgressionMapping,
    SimConfig,
    UpgradeTable,
)
from simulation.orchestrator import create_initial_state, run_simulation


@pytest.fixture
def full_config():
    """Create complete simulation configuration for orchestrator tests."""
    pack_config_1 = PackConfig(
        name="basic_pack",
        card_types_table={
            0: CardTypesRange(min=2, max=2),
            10: CardTypesRange(min=3, max=3),
            25: CardTypesRange(min=4, max=4),
        },
    )
    pack_config_2 = PackConfig(
        name="premium_pack",
        card_types_table={
            0: CardTypesRange(min=3, max=3),
            10: CardTypesRange(min=4, max=4),
            25: CardTypesRange(min=5, max=5),
        },
    )

    gold_upgrade_table = UpgradeTable(
        category=CardCategory.GOLD_SHARED,
        duplicate_costs=[50] * 100,
        coin_costs=[200] * 100,
        bluestar_rewards=[10] * 100,
    )
    blue_upgrade_table = UpgradeTable(
        category=CardCategory.BLUE_SHARED,
        duplicate_costs=[50] * 100,
        coin_costs=[200] * 100,
        bluestar_rewards=[10] * 100,
    )
    unique_upgrade_table = UpgradeTable(
        category=CardCategory.UNIQUE,
        duplicate_costs=[30] * 10,
        coin_costs=[150] * 10,
        bluestar_rewards=[5] * 10,
    )

    gold_dup_range = DuplicateRange(
        category=CardCategory.GOLD_SHARED,
        min_pct=[0.8] * 100,
        max_pct=[1.2] * 100,
    )
    blue_dup_range = DuplicateRange(
        category=CardCategory.BLUE_SHARED,
        min_pct=[0.8] * 100,
        max_pct=[1.2] * 100,
    )
    unique_dup_range = DuplicateRange(
        category=CardCategory.UNIQUE,
        min_pct=[0.8] * 10,
        max_pct=[1.2] * 10,
    )

    gold_coin_per_dup = CoinPerDuplicate(
        category=CardCategory.GOLD_SHARED,
        coins_per_dupe=[2] * 100,
    )
    blue_coin_per_dup = CoinPerDuplicate(
        category=CardCategory.BLUE_SHARED,
        coins_per_dupe=[2] * 100,
    )
    unique_coin_per_dup = CoinPerDuplicate(
        category=CardCategory.UNIQUE,
        coins_per_dupe=[5] * 10,
    )

    progression_mapping = ProgressionMapping(
        shared_levels=[1, 5, 10, 20, 40, 60, 80],
        unique_levels=[1, 2, 3, 4, 6, 8, 10],
    )

    return SimConfig(
        packs=[pack_config_1, pack_config_2],
        upgrade_tables={
            CardCategory.GOLD_SHARED: gold_upgrade_table,
            CardCategory.BLUE_SHARED: blue_upgrade_table,
            CardCategory.UNIQUE: unique_upgrade_table,
        },
        duplicate_ranges={
            CardCategory.GOLD_SHARED: gold_dup_range,
            CardCategory.BLUE_SHARED: blue_dup_range,
            CardCategory.UNIQUE: unique_dup_range,
        },
        coin_per_duplicate={
            CardCategory.GOLD_SHARED: gold_coin_per_dup,
            CardCategory.BLUE_SHARED: blue_coin_per_dup,
            CardCategory.UNIQUE: unique_coin_per_dup,
        },
        progression_mapping=progression_mapping,
        unique_unlock_schedule={1: 8, 5: 2},
        daily_pack_schedule=[{"basic_pack": 2.0, "premium_pack": 1.5}],
        num_days=1,
        max_shared_level=100,
        max_unique_level=10,
    )


def test_oneday_simulation(full_config):
    """Test: 1-day deterministic simulation produces valid snapshot."""
    result = run_simulation(full_config, rng=None)

    assert len(result.daily_snapshots) == 1

    snapshot = result.daily_snapshots[0]
    assert snapshot.day == 1
    assert snapshot.total_bluestars >= 0
    assert snapshot.bluestars_earned_today >= 0
    assert snapshot.coins_balance >= 0
    assert snapshot.coins_earned_today >= 0
    assert snapshot.coins_spent_today >= 0
    assert (
        len(snapshot.card_levels)
        == full_config.num_gold_cards + full_config.num_blue_cards + 8
    )
    assert snapshot.total_unique_unlocked == 8
    assert "GOLD_SHARED" in snapshot.category_avg_levels
    assert "BLUE_SHARED" in snapshot.category_avg_levels
    assert "UNIQUE" in snapshot.category_avg_levels


def test_duplicates_accumulate(full_config):
    """Test: card duplicates accumulate across days."""
    full_config.num_days = 5

    result = run_simulation(full_config, rng=None)

    assert len(result.daily_snapshots) == 5

    day1_snapshot = result.daily_snapshots[0]
    day5_snapshot = result.daily_snapshots[4]

    day1_total_level = sum(day1_snapshot.card_levels.values())
    day5_total_level = sum(day5_snapshot.card_levels.values())

    assert day5_total_level >= day1_total_level


def test_upgrades_fire(full_config):
    """Test: upgrades fire when threshold crossed on day 3."""
    full_config.num_days = 5
    full_config.daily_pack_schedule = [{"basic_pack": 5.0, "premium_pack": 5.0}]

    result = run_simulation(full_config, rng=None)

    total_upgrades_count = 0
    for snapshot in result.daily_snapshots:
        total_upgrades_count += len(snapshot.upgrades_today)

    assert total_upgrades_count > 0


def test_unlock_schedule(full_config):
    """Test: unique cards appear on scheduled days {1: 8, 5: 2}."""
    full_config.num_days = 6

    result = run_simulation(full_config, rng=None)

    day1_snapshot = result.daily_snapshots[0]
    assert day1_snapshot.total_unique_unlocked == 8

    day4_snapshot = result.daily_snapshots[3]
    assert day4_snapshot.total_unique_unlocked == 8

    day5_snapshot = result.daily_snapshots[4]
    assert day5_snapshot.total_unique_unlocked == 10

    day6_snapshot = result.daily_snapshots[5]
    assert day6_snapshot.total_unique_unlocked == 10


def test_bluestar_accounting(full_config):
    """Test: total_bluestars = sum of all upgrade rewards across all days."""
    full_config.num_days = 10
    full_config.daily_pack_schedule = [{"basic_pack": 5.0, "premium_pack": 5.0}]

    result = run_simulation(full_config, rng=None)

    total_bluestars_from_snapshots = sum(
        snapshot.bluestars_earned_today for snapshot in result.daily_snapshots
    )

    assert result.total_bluestars == total_bluestars_from_snapshots


def test_coin_balance(full_config):
    """Test: coins_balance = total_income - total_spent."""
    full_config.num_days = 10

    result = run_simulation(full_config, rng=None)

    final_snapshot = result.daily_snapshots[-1]

    assert (
        final_snapshot.coins_balance
        == result.total_coins_earned - result.total_coins_spent
    )


def test_performance_100days(full_config):
    """Test: 100-day simulation completes in < 30 seconds."""
    full_config.num_days = 100

    start_time = time.time()
    result = run_simulation(full_config, rng=None)
    elapsed_time = time.time() - start_time

    assert len(result.daily_snapshots) == 100
    assert elapsed_time < 30.0


def test_initial_state_setup(full_config):
    """Test: create_initial_state sets up correct card counts."""
    game_state, coin_ledger, streak_state = create_initial_state(full_config)

    gold_cards = [c for c in game_state.cards if c.category == CardCategory.GOLD_SHARED]
    blue_cards = [c for c in game_state.cards if c.category == CardCategory.BLUE_SHARED]
    unique_cards = [c for c in game_state.cards if c.category == CardCategory.UNIQUE]

    assert len(gold_cards) == full_config.num_gold_cards
    assert len(blue_cards) == full_config.num_blue_cards
    assert len(unique_cards) == 8

    assert all(c.level == 1 for c in game_state.cards)
    assert all(c.duplicates == 0 for c in game_state.cards)

    assert coin_ledger.balance == 0
    assert streak_state.streak_shared == 0
    assert streak_state.streak_unique == 0
