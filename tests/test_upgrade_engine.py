"""
Tests for the upgrade engine module.

Covers priority ordering, resource checks, progression gating, and bluestar rewards.
"""

import pytest

from simulation.coin_economy import CoinLedger
from simulation.models import (
    Card,
    CardCategory,
    GameState,
    ProgressionMapping,
    SimConfig,
    StreakState,
    UpgradeTable,
)
from simulation.upgrade_engine import (
    UpgradeEvent,
    attempt_upgrades,
    get_upgrade_candidates,
)


@pytest.fixture
def base_config():
    """Create basic simulation config with upgrade tables."""
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

    progression_mapping = ProgressionMapping(
        shared_levels=[1, 5, 10, 20, 40, 60, 80],
        unique_levels=[1, 2, 3, 4, 6, 8, 10],
    )

    return SimConfig(
        packs=[],
        upgrade_tables={
            CardCategory.GOLD_SHARED: gold_upgrade_table,
            CardCategory.BLUE_SHARED: blue_upgrade_table,
            CardCategory.UNIQUE: unique_upgrade_table,
        },
        duplicate_ranges={},
        coin_per_duplicate={},
        progression_mapping=progression_mapping,
        unique_unlock_schedule={},
        pack_averages={},
        num_days=100,
        max_shared_level=100,
        max_unique_level=10,
    )


@pytest.fixture
def base_game_state():
    """Create basic game state."""
    return GameState(
        day=1,
        cards=[],
        coins=0,
        total_bluestars=0,
        streak_state=StreakState(streak_shared=0, streak_unique=0),
    )


def test_upgrade_success(base_config, base_game_state):
    """Test successful upgrade when all conditions met."""
    card = Card(
        id="card_1",
        name="Gold Card",
        category=CardCategory.GOLD_SHARED,
        level=5,
        duplicates=100,
    )
    base_game_state.cards = [card]
    ledger = CoinLedger(balance=500)

    events = attempt_upgrades(base_game_state, base_config, ledger)

    assert len(events) == 2
    assert events[0].card_id == "card_1"
    assert events[0].old_level == 5
    assert events[0].new_level == 6
    assert events[1].old_level == 6
    assert events[1].new_level == 7
    assert card.level == 7
    assert card.duplicates == 0
    assert ledger.balance == 100
    assert base_game_state.total_bluestars == 20


def test_blocked_by_duplicates(base_config, base_game_state):
    """Test upgrade blocked by insufficient duplicates."""
    card = Card(
        id="card_1",
        name="Gold Card",
        category=CardCategory.GOLD_SHARED,
        level=5,
        duplicates=40,
    )
    base_game_state.cards = [card]
    ledger = CoinLedger(balance=500)

    events = attempt_upgrades(base_game_state, base_config, ledger)

    assert len(events) == 0
    assert card.level == 5
    assert card.duplicates == 40
    assert ledger.balance == 500
    assert base_game_state.total_bluestars == 0


def test_blocked_by_coins(base_config, base_game_state):
    """Test upgrade blocked by insufficient coins."""
    card = Card(
        id="card_1",
        name="Gold Card",
        category=CardCategory.GOLD_SHARED,
        level=5,
        duplicates=100,
    )
    base_game_state.cards = [card]
    ledger = CoinLedger(balance=150)

    events = attempt_upgrades(base_game_state, base_config, ledger)

    assert len(events) == 0
    assert card.level == 5
    assert card.duplicates == 100
    assert ledger.balance == 150
    assert base_game_state.total_bluestars == 0


def test_blocked_by_gating(base_config, base_game_state):
    """Test unique upgrade blocked by progression gating."""
    unique_card = Card(
        id="unique_1",
        name="Unique Card",
        category=CardCategory.UNIQUE,
        level=3,
        duplicates=999,
    )
    gold_card = Card(
        id="gold_1",
        name="Gold Card",
        category=CardCategory.GOLD_SHARED,
        level=10,
        duplicates=0,
    )
    blue_card = Card(
        id="blue_1",
        name="Blue Card",
        category=CardCategory.BLUE_SHARED,
        level=10,
        duplicates=0,
    )

    base_game_state.cards = [unique_card, gold_card, blue_card]
    ledger = CoinLedger(balance=99999)

    events = attempt_upgrades(base_game_state, base_config, ledger)

    assert len(events) == 0
    assert unique_card.level == 3


def test_priority_order_unique_first(base_config, base_game_state):
    """Test priority order: Unique > Gold > Blue."""
    unique_card = Card(
        id="unique_1",
        name="Unique Card",
        category=CardCategory.UNIQUE,
        level=2,
        duplicates=50,
    )
    gold_card = Card(
        id="gold_1",
        name="Gold Card",
        category=CardCategory.GOLD_SHARED,
        level=5,
        duplicates=100,
    )
    blue_card = Card(
        id="blue_1",
        name="Blue Card",
        category=CardCategory.BLUE_SHARED,
        level=50,
        duplicates=100,
    )

    base_game_state.cards = [blue_card, gold_card, unique_card]
    ledger = CoinLedger(balance=200)

    events = attempt_upgrades(base_game_state, base_config, ledger)

    assert len(events) == 1
    assert events[0].card_id == "unique_1"
    assert unique_card.level == 3
    assert gold_card.level == 5
    assert blue_card.level == 50


def test_within_category_ordering(base_config, base_game_state):
    """Test within-category ordering: lowest level first."""
    gold_card_high = Card(
        id="gold_high",
        name="Gold High",
        category=CardCategory.GOLD_SHARED,
        level=20,
        duplicates=100,
    )
    gold_card_low = Card(
        id="gold_low",
        name="Gold Low",
        category=CardCategory.GOLD_SHARED,
        level=5,
        duplicates=100,
    )
    gold_card_mid = Card(
        id="gold_mid",
        name="Gold Mid",
        category=CardCategory.GOLD_SHARED,
        level=10,
        duplicates=100,
    )

    base_game_state.cards = [gold_card_high, gold_card_mid, gold_card_low]
    ledger = CoinLedger(balance=1000)

    candidates = get_upgrade_candidates(base_game_state, base_config)

    assert candidates[0].id == "gold_low"
    assert candidates[1].id == "gold_mid"
    assert candidates[2].id == "gold_high"


def test_multiple_upgrades_per_day(base_config, base_game_state):
    """Test multiple upgrades in single attempt_upgrades call."""
    card_1 = Card(
        id="card_1",
        name="Gold Card 1",
        category=CardCategory.GOLD_SHARED,
        level=5,
        duplicates=100,
    )
    card_2 = Card(
        id="card_2",
        name="Gold Card 2",
        category=CardCategory.GOLD_SHARED,
        level=5,
        duplicates=100,
    )

    base_game_state.cards = [card_1, card_2]
    ledger = CoinLedger(balance=500)

    events = attempt_upgrades(base_game_state, base_config, ledger)

    assert len(events) == 2
    assert card_1.level == 6
    assert card_2.level == 6
    assert ledger.balance == 100


def test_bluestar_accumulation(base_config, base_game_state):
    """Test bluestar accumulation across multiple upgrades."""
    card_1 = Card(
        id="card_1",
        name="Card 1",
        category=CardCategory.GOLD_SHARED,
        level=1,
        duplicates=200,
    )
    card_2 = Card(
        id="card_2",
        name="Card 2",
        category=CardCategory.GOLD_SHARED,
        level=1,
        duplicates=200,
    )
    card_3 = Card(
        id="card_3",
        name="Card 3",
        category=CardCategory.GOLD_SHARED,
        level=1,
        duplicates=200,
    )

    base_game_state.cards = [card_1, card_2, card_3]
    ledger = CoinLedger(balance=1000)

    events = attempt_upgrades(base_game_state, base_config, ledger)

    assert len(events) == 5
    total_bluestars = sum(e.bluestars_earned for e in events)
    assert total_bluestars == 50
    assert base_game_state.total_bluestars == 50


def test_maxed_card_not_eligible(base_config, base_game_state):
    """Test maxed unique card is not upgraded."""
    unique_card = Card(
        id="unique_1",
        name="Unique Card",
        category=CardCategory.UNIQUE,
        level=10,
        duplicates=999,
    )
    gold_card = Card(
        id="gold_1",
        name="Gold Card",
        category=CardCategory.GOLD_SHARED,
        level=100,
        duplicates=0,
    )

    base_game_state.cards = [unique_card, gold_card]
    ledger = CoinLedger(balance=99999)

    events = attempt_upgrades(base_game_state, base_config, ledger)

    assert len(events) == 0
    assert unique_card.level == 10
    assert gold_card.level == 100


def test_maxed_shared_card_not_eligible(base_config, base_game_state):
    """Test maxed shared card is not upgraded."""
    gold_card = Card(
        id="gold_1",
        name="Gold Card",
        category=CardCategory.GOLD_SHARED,
        level=100,
        duplicates=999,
    )

    base_game_state.cards = [gold_card]
    ledger = CoinLedger(balance=99999)

    events = attempt_upgrades(base_game_state, base_config, ledger)

    assert len(events) == 0
    assert gold_card.level == 100


def test_upgrade_loop_continues_until_blocked(base_config, base_game_state):
    """Test upgrade loop continues until resources exhausted."""
    card = Card(
        id="card_1",
        name="Gold Card",
        category=CardCategory.GOLD_SHARED,
        level=1,
        duplicates=250,
    )

    base_game_state.cards = [card]
    ledger = CoinLedger(balance=1000)

    events = attempt_upgrades(base_game_state, base_config, ledger)

    assert len(events) == 5
    assert card.level == 6
    assert card.duplicates == 0
    assert ledger.balance == 0
