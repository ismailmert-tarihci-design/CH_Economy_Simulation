"""
Tests for Phase 1 of Card Drop Algorithm: Rarity Decision.

Verifies the 5-step weighted algorithm with progression gap balancing
and streak penalties.
"""

from random import Random

import pytest

from simulation.drop_algorithm import (
    GAP_BASE,
    STREAK_DECAY_SHARED,
    STREAK_DECAY_UNIQUE,
    decide_rarity,
    update_rarity_streak,
)
from simulation.models import (
    Card,
    CardCategory,
    GameState,
    ProgressionMapping,
    SimConfig,
    StreakState,
)


@pytest.fixture
def base_config():
    """Create minimal SimConfig for testing."""
    return SimConfig(
        packs=[],
        upgrade_tables={},
        duplicate_ranges={},
        coin_per_duplicate={},
        progression_mapping=ProgressionMapping(
            shared_levels=[1, 5, 10, 20, 40, 60, 80, 100],
            unique_levels=[1, 2, 3, 4, 5, 6, 7, 10],
        ),
        unique_unlock_schedule={},
        pack_averages={},
        num_days=100,
        base_shared_rate=0.70,
        base_unique_rate=0.30,
    )


@pytest.fixture
def zero_streak():
    """Create StreakState with no streaks."""
    return StreakState(
        streak_shared=0,
        streak_unique=0,
        streak_per_color={},
        streak_per_hero={},
    )


def test_balanced_state_distribution(base_config, zero_streak):
    """
    Test 1: Balanced state should yield ~70/30 shared/unique distribution.

    Setup:
    - All shared cards at level 50/100 (0.5 progression)
    - All unique at level 5/10 (0.5 progression)
    - Zero streaks

    Expected: ~70% shared, ~30% unique over 10,000 rolls
    """
    cards = [
        Card(id="g1", name="Gold1", category=CardCategory.GOLD_SHARED, level=50),
        Card(id="g2", name="Gold2", category=CardCategory.GOLD_SHARED, level=50),
        Card(id="b1", name="Blue1", category=CardCategory.BLUE_SHARED, level=50),
        Card(id="b2", name="Blue2", category=CardCategory.BLUE_SHARED, level=50),
        Card(id="u1", name="Unique1", category=CardCategory.UNIQUE, level=5),
        Card(id="u2", name="Unique2", category=CardCategory.UNIQUE, level=5),
    ]

    game_state = GameState(
        day=1,
        cards=cards,
        coins=0,
        total_bluestars=0,
        streak_state=zero_streak,
    )

    rng = Random(42)
    num_rolls = 10000
    shared_count = 0

    for _ in range(num_rolls):
        result = decide_rarity(game_state, base_config, zero_streak, rng)
        if result == CardCategory.GOLD_SHARED:
            shared_count += 1

    shared_ratio = shared_count / num_rolls

    assert 0.67 <= shared_ratio <= 0.73, (
        f"Expected shared ratio ~0.70, got {shared_ratio:.3f}"
    )


def test_positive_gap_catches_up_shared(base_config, zero_streak):
    """
    Test 2: Positive gap (Unique ahead) should increase shared probability.

    Setup:
    - SUnique=0.8, SShared=0.2 → Gap=0.6

    Expected: ProbShared > 0.75 (system catches up shared cards)
    """
    cards = [
        Card(id="g1", name="Gold1", category=CardCategory.GOLD_SHARED, level=10),
        Card(id="b1", name="Blue1", category=CardCategory.BLUE_SHARED, level=30),
        Card(id="u1", name="Unique1", category=CardCategory.UNIQUE, level=8),
        Card(id="u2", name="Unique2", category=CardCategory.UNIQUE, level=8),
    ]

    game_state = GameState(
        day=1,
        cards=cards,
        coins=0,
        total_bluestars=0,
        streak_state=zero_streak,
    )

    rng = Random(42)
    num_rolls = 10000
    shared_count = sum(
        1
        for _ in range(num_rolls)
        if decide_rarity(game_state, base_config, zero_streak, rng)
        == CardCategory.GOLD_SHARED
    )

    prob_shared = shared_count / num_rolls
    assert prob_shared > 0.75, (
        f"Expected ProbShared > 0.75 when Unique ahead, got {prob_shared:.3f}"
    )


def test_negative_gap_catches_up_unique(base_config, zero_streak):
    """
    Test 3: Negative gap (Shared ahead) should increase unique probability.

    Setup:
    - SShared=0.8, SUnique=0.2 → Gap=-0.6

    Expected: ProbUnique > 0.35 (system catches up unique cards)
    """
    cards = [
        Card(id="g1", name="Gold1", category=CardCategory.GOLD_SHARED, level=80),
        Card(id="b1", name="Blue1", category=CardCategory.BLUE_SHARED, level=80),
        Card(id="u1", name="Unique1", category=CardCategory.UNIQUE, level=2),
        Card(id="u2", name="Unique2", category=CardCategory.UNIQUE, level=2),
    ]

    game_state = GameState(
        day=1,
        cards=cards,
        coins=0,
        total_bluestars=0,
        streak_state=zero_streak,
    )

    rng = Random(42)
    num_rolls = 10000
    unique_count = sum(
        1
        for _ in range(num_rolls)
        if decide_rarity(game_state, base_config, zero_streak, rng)
        == CardCategory.UNIQUE
    )

    prob_unique = unique_count / num_rolls
    assert prob_unique > 0.35, (
        f"Expected ProbUnique > 0.35 when Shared ahead, got {prob_unique:.3f}"
    )


def test_shared_streak_penalty(base_config, zero_streak):
    """
    Test 4: Shared streak penalty should reduce shared probability.

    Setup:
    - Balanced progression (Gap=0)
    - streak_shared=3

    Expected: ProbShared < 0.40
    Formula: 0.7 * (0.6^3) = 0.7 * 0.216 = 0.1512
    After normalization with unique: ~0.34
    """
    cards = [
        Card(id="g1", name="Gold1", category=CardCategory.GOLD_SHARED, level=50),
        Card(id="b1", name="Blue1", category=CardCategory.BLUE_SHARED, level=50),
        Card(id="u1", name="Unique1", category=CardCategory.UNIQUE, level=5),
    ]

    game_state = GameState(
        day=1,
        cards=cards,
        coins=0,
        total_bluestars=0,
        streak_state=zero_streak,
    )

    streak_state = StreakState(
        streak_shared=3,
        streak_unique=0,
        streak_per_color={},
        streak_per_hero={},
    )

    rng = Random(42)
    num_rolls = 10000
    shared_count = sum(
        1
        for _ in range(num_rolls)
        if decide_rarity(game_state, base_config, streak_state, rng)
        == CardCategory.GOLD_SHARED
    )

    prob_shared = shared_count / num_rolls
    assert prob_shared < 0.40, (
        f"Expected ProbShared < 0.40 with streak_shared=3, got {prob_shared:.3f}"
    )


def test_unique_streak_penalty(base_config, zero_streak):
    """
    Test 5: Unique streak penalty should reduce unique probability.

    Setup:
    - Balanced progression (Gap=0)
    - streak_unique=3

    Expected: ProbUnique < 0.05
    Formula: 0.3 * (0.3^3) = 0.3 * 0.027 = 0.0081
    After normalization: ~0.011
    """
    cards = [
        Card(id="g1", name="Gold1", category=CardCategory.GOLD_SHARED, level=50),
        Card(id="b1", name="Blue1", category=CardCategory.BLUE_SHARED, level=50),
        Card(id="u1", name="Unique1", category=CardCategory.UNIQUE, level=5),
    ]

    game_state = GameState(
        day=1,
        cards=cards,
        coins=0,
        total_bluestars=0,
        streak_state=zero_streak,
    )

    streak_state = StreakState(
        streak_shared=0,
        streak_unique=3,
        streak_per_color={},
        streak_per_hero={},
    )

    rng = Random(42)
    num_rolls = 10000
    unique_count = sum(
        1
        for _ in range(num_rolls)
        if decide_rarity(game_state, base_config, streak_state, rng)
        == CardCategory.UNIQUE
    )

    prob_unique = unique_count / num_rolls
    assert prob_unique < 0.05, (
        f"Expected ProbUnique < 0.05 with streak_unique=3, got {prob_unique:.3f}"
    )


def test_deterministic_mode(base_config, zero_streak):
    """
    Test 6: Deterministic mode should choose majority category.

    Setup:
    - Balanced state (ProbShared ~0.7)
    - rng=None

    Expected: Always returns GOLD_SHARED (majority)
    """
    cards = [
        Card(id="g1", name="Gold1", category=CardCategory.GOLD_SHARED, level=50),
        Card(id="b1", name="Blue1", category=CardCategory.BLUE_SHARED, level=50),
        Card(id="u1", name="Unique1", category=CardCategory.UNIQUE, level=5),
    ]

    game_state = GameState(
        day=1,
        cards=cards,
        coins=0,
        total_bluestars=0,
        streak_state=zero_streak,
    )

    for _ in range(100):
        result = decide_rarity(game_state, base_config, zero_streak, rng=None)
        assert result == CardCategory.GOLD_SHARED, (
            "Deterministic mode with ProbShared>0.5 should always return GOLD_SHARED"
        )


def test_streak_update_shared(zero_streak):
    """
    Test 7a: Choosing shared card updates streaks correctly.

    Expected:
    - streak_shared increments
    - streak_unique resets to 0
    """
    updated = update_rarity_streak(zero_streak, CardCategory.GOLD_SHARED)

    assert updated.streak_shared == 1
    assert updated.streak_unique == 0

    updated2 = update_rarity_streak(updated, CardCategory.BLUE_SHARED)
    assert updated2.streak_shared == 2
    assert updated2.streak_unique == 0


def test_streak_update_unique(zero_streak):
    """
    Test 7b: Choosing unique card updates streaks correctly.

    Expected:
    - streak_unique increments
    - streak_shared resets to 0
    """
    updated = update_rarity_streak(zero_streak, CardCategory.UNIQUE)

    assert updated.streak_unique == 1
    assert updated.streak_shared == 0

    updated2 = update_rarity_streak(updated, CardCategory.UNIQUE)
    assert updated2.streak_unique == 2
    assert updated2.streak_shared == 0


def test_streak_update_alternating():
    """
    Test 7c: Alternating between shared and unique resets streaks.

    Expected: Streaks reset when switching category
    """
    state = StreakState(
        streak_shared=5,
        streak_unique=0,
        streak_per_color={},
        streak_per_hero={},
    )

    state = update_rarity_streak(state, CardCategory.UNIQUE)
    assert state.streak_unique == 1
    assert state.streak_shared == 0

    state = update_rarity_streak(state, CardCategory.GOLD_SHARED)
    assert state.streak_shared == 1
    assert state.streak_unique == 0


def test_constants_exported():
    """
    Test 8: Verify constants are exported at module level.
    """
    assert STREAK_DECAY_SHARED == 0.6
    assert STREAK_DECAY_UNIQUE == 0.3
    assert GAP_BASE == 1.5


def test_empty_card_list_safe(base_config, zero_streak):
    """
    Test 9: Empty card list should not crash (edge case).

    Expected: Returns valid result with default probabilities (70/30)
    """
    game_state = GameState(
        day=1,
        cards=[],
        coins=0,
        total_bluestars=0,
        streak_state=zero_streak,
    )

    rng = Random(42)
    num_rolls = 10000
    shared_count = sum(
        1
        for _ in range(num_rolls)
        if decide_rarity(game_state, base_config, zero_streak, rng)
        == CardCategory.GOLD_SHARED
    )

    shared_ratio = shared_count / num_rolls
    assert 0.67 <= shared_ratio <= 0.73, (
        f"Empty card list should use base rates (~0.70), got {shared_ratio:.3f}"
    )
