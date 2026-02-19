"""
Tests for Card Drop Algorithm: Phase 1 (Rarity Decision) and Phase 2 (Card Selection).

Verifies the complete drop algorithm including rarity decision,
card selection within category, streak updates, and duplicate calculation.
"""

from random import Random

import pytest

from simulation.drop_algorithm import (
    GAP_BASE,
    STREAK_DECAY_SHARED,
    STREAK_DECAY_UNIQUE,
    compute_duplicates_received,
    decide_rarity,
    perform_card_pull,
    select_shared_card,
    select_unique_card,
    update_card_streak,
    update_rarity_streak,
)
from simulation.models import (
    Card,
    CardCategory,
    CoinPerDuplicate,
    DuplicateRange,
    GameState,
    ProgressionMapping,
    SimConfig,
    StreakState,
    UpgradeTable,
)


@pytest.fixture
def base_config():
    """Create minimal SimConfig for testing."""
    return SimConfig(
        packs=[],
        upgrade_tables={
            CardCategory.GOLD_SHARED: UpgradeTable(
                category=CardCategory.GOLD_SHARED,
                duplicate_costs=[10, 15, 20, 25, 30, 40, 50],
                coin_costs=[100, 200, 300, 400, 500, 600, 700],
                bluestar_rewards=[1, 2, 3, 4, 5, 6, 7],
            ),
            CardCategory.BLUE_SHARED: UpgradeTable(
                category=CardCategory.BLUE_SHARED,
                duplicate_costs=[10, 15, 20, 25, 30, 40, 50],
                coin_costs=[100, 200, 300, 400, 500, 600, 700],
                bluestar_rewards=[1, 2, 3, 4, 5, 6, 7],
            ),
            CardCategory.UNIQUE: UpgradeTable(
                category=CardCategory.UNIQUE,
                duplicate_costs=[5, 8, 12, 16, 20, 25, 30, 35, 40],
                coin_costs=[50, 100, 150, 200, 250, 300, 350, 400, 450],
                bluestar_rewards=[2, 3, 4, 5, 6, 7, 8, 9, 10],
            ),
        },
        duplicate_ranges={
            CardCategory.GOLD_SHARED: DuplicateRange(
                category=CardCategory.GOLD_SHARED,
                min_pct=[0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8],
                max_pct=[1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2],
            ),
            CardCategory.BLUE_SHARED: DuplicateRange(
                category=CardCategory.BLUE_SHARED,
                min_pct=[0.8, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8],
                max_pct=[1.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.2],
            ),
            CardCategory.UNIQUE: DuplicateRange(
                category=CardCategory.UNIQUE,
                min_pct=[0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9],
                max_pct=[1.1, 1.1, 1.1, 1.1, 1.1, 1.1, 1.1, 1.1, 1.1],
            ),
        },
        coin_per_duplicate={
            CardCategory.GOLD_SHARED: CoinPerDuplicate(
                category=CardCategory.GOLD_SHARED,
                coins_per_dupe=[5, 6, 7, 8, 9, 10, 11],
            ),
            CardCategory.BLUE_SHARED: CoinPerDuplicate(
                category=CardCategory.BLUE_SHARED,
                coins_per_dupe=[5, 6, 7, 8, 9, 10, 11],
            ),
            CardCategory.UNIQUE: CoinPerDuplicate(
                category=CardCategory.UNIQUE,
                coins_per_dupe=[10, 12, 14, 16, 18, 20, 22, 24, 26],
            ),
        },
        progression_mapping=ProgressionMapping(
            shared_levels=[1, 5, 10, 20, 40, 60, 80, 100],
            unique_levels=[1, 2, 3, 4, 5, 6, 7, 10],
        ),
        unique_unlock_schedule={},
        daily_pack_schedule=[],
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
    - All shared cards at level 40/100
    - All unique at level 5/10
    - Per the test mapping (shared=40 ↔ unique=5), these are balanced
    - Zero streaks

    Expected: ~70% shared, ~30% unique over 10,000 rolls
    """
    cards = [
        Card(id="g1", name="Gold1", category=CardCategory.GOLD_SHARED, level=40),
        Card(id="g2", name="Gold2", category=CardCategory.GOLD_SHARED, level=40),
        Card(id="b1", name="Blue1", category=CardCategory.BLUE_SHARED, level=40),
        Card(id="b2", name="Blue2", category=CardCategory.BLUE_SHARED, level=40),
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
    - Near-balanced progression (shared=50, unique=5, slight negative gap)
    - streak_unique=3

    Expected: ProbUnique < 0.15 (significantly below no-streak unique rate)
    With linear ratio: raw_ratio ≈ 0.34, unique_weight ≈ 0.66
    After streak decay: 0.66 * 0.3^3 ≈ 0.018 → prob_unique ≈ 0.05-0.10
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
    assert prob_unique < 0.15, (
        f"Expected ProbUnique < 0.15 with streak_unique=3, got {prob_unique:.3f}"
    )


def test_deterministic_mode(base_config, zero_streak):
    """
    Test 6: Deterministic mode should choose majority category.

    Setup:
    - Balanced state per mapping (shared=40, unique=5 → ProbShared ~0.7)
    - rng=None

    Expected: Always returns GOLD_SHARED (majority)
    """
    cards = [
        Card(id="g1", name="Gold1", category=CardCategory.GOLD_SHARED, level=40),
        Card(id="b1", name="Blue1", category=CardCategory.BLUE_SHARED, level=40),
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
    assert shared_ratio >= 0.67 and shared_ratio <= 0.73, (
        f"Empty card list should use base rates (~0.70), got {shared_ratio:.3f}"
    )


def test_shared_card_level_weighting(base_config, zero_streak):
    """
    Test 10 (Phase 2): Level weighting in shared card selection.

    Setup:
    - 5 shared cards at levels [1, 5, 10, 20, 50]
    - Zero color streaks
    - 1000 MC selections

    Expected:
    - Level-1 card selected most often (~50% of selections)
    - Level-50 card selected least often (<5% of selections)

    Weight formula: 1/(level+1)
    - Level 1: 1/2 = 0.5
    - Level 5: 1/6 = 0.167
    - Level 10: 1/11 = 0.091
    - Level 20: 1/21 = 0.048
    - Level 50: 1/51 = 0.020
    Total weight = 0.826
    Level 1 expected ratio = 0.5 / 0.826 = 60.5%
    Level 50 expected ratio = 0.020 / 0.826 = 2.4%
    """
    cards = [
        Card(id="g1", name="Gold1", category=CardCategory.GOLD_SHARED, level=1),
        Card(id="g2", name="Gold2", category=CardCategory.GOLD_SHARED, level=5),
        Card(id="g3", name="Gold3", category=CardCategory.GOLD_SHARED, level=10),
        Card(id="b1", name="Blue1", category=CardCategory.BLUE_SHARED, level=20),
        Card(id="b2", name="Blue2", category=CardCategory.BLUE_SHARED, level=50),
    ]

    game_state = GameState(
        day=1,
        cards=cards,
        coins=0,
        total_bluestars=0,
        streak_state=zero_streak,
    )

    rng = Random(42)
    num_selections = 1000
    counts = {card.id: 0 for card in cards}

    for _ in range(num_selections):
        selected = select_shared_card(game_state, base_config, zero_streak, rng)
        counts[selected.id] += 1

    ratio_level1 = counts["g1"] / num_selections
    ratio_level50 = counts["b2"] / num_selections

    assert ratio_level1 > 0.50, (
        f"Level-1 card should be selected >50%, got {ratio_level1:.3f}"
    )
    assert ratio_level50 < 0.05, (
        f"Level-50 card should be selected <5%, got {ratio_level50:.3f}"
    )


def test_shared_card_color_streak_penalty(base_config, zero_streak):
    """
    Test 11 (Phase 2): Color streak penalty in shared card selection.

    Setup:
    - 2 Gold cards (both level 1)
    - 1 Blue card (level 1)
    - streak_per_color = {"GOLD_SHARED": 3, "BLUE_SHARED": 0}
    - 100 MC selections

    Expected:
    - Blue card selected significantly more often
    - Gold cards penalized by 0.6^3 = 0.216

    Weights:
    - Each Gold: (1/2) * 0.216 = 0.108
    - Blue: (1/2) * 1.0 = 0.5
    Total: 0.716
    Blue expected ratio = 0.5 / 0.716 = 69.8%
    """
    cards = [
        Card(id="g1", name="Gold1", category=CardCategory.GOLD_SHARED, level=1),
        Card(id="g2", name="Gold2", category=CardCategory.GOLD_SHARED, level=1),
        Card(id="b1", name="Blue1", category=CardCategory.BLUE_SHARED, level=1),
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
        streak_unique=0,
        streak_per_color={"GOLD_SHARED": 3, "BLUE_SHARED": 0},
        streak_per_hero={},
    )

    rng = Random(42)
    num_selections = 100
    blue_count = 0

    for _ in range(num_selections):
        selected = select_shared_card(game_state, base_config, streak_state, rng)
        if selected.category == CardCategory.BLUE_SHARED:
            blue_count += 1

    blue_ratio = blue_count / num_selections
    assert blue_ratio > 0.60, (
        f"Blue card should be selected >60% due to Gold streak penalty, got {blue_ratio:.2f}"
    )


def test_unique_card_hero_streak_penalty(base_config, zero_streak):
    """
    Test 12 (Phase 2): Hero streak penalty in unique card selection.

    Setup:
    - 3 unique cards (all level 1)
    - streak_per_hero = {card1.id: 3, card2.id: 0, card3.id: 0}
    - 100 MC selections

    Expected:
    - card1 selected least often due to hero streak penalty
    - card1 penalized by streak_decay_unique^3 = 0.3^3 = 0.027

    Weights:
    - card1: (1/2) * 0.027 = 0.0135
    - card2: (1/2) * 1.0 = 0.5
    - card3: (1/2) * 1.0 = 0.5
    Total: 1.0135
    card1 expected ratio = 0.0135 / 1.0135 = 1.3%
    """
    cards = [
        Card(id="u1", name="Unique1", category=CardCategory.UNIQUE, level=1),
        Card(id="u2", name="Unique2", category=CardCategory.UNIQUE, level=1),
        Card(id="u3", name="Unique3", category=CardCategory.UNIQUE, level=1),
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
        streak_unique=0,
        streak_per_color={},
        streak_per_hero={"u1": 3, "u2": 0, "u3": 0},
    )

    rng = Random(42)
    num_selections = 100
    u1_count = 0

    for _ in range(num_selections):
        selected = select_unique_card(game_state, base_config, streak_state, rng)
        if selected.id == "u1":
            u1_count += 1

    u1_ratio = u1_count / num_selections
    assert u1_ratio < 0.20, (
        f"card1 should be selected <20% due to hero streak penalty, got {u1_ratio:.2f}"
    )


def test_deterministic_card_selection(base_config, zero_streak):
    """
    Test 13 (Phase 2): Deterministic mode picks highest weighted card.

    Setup:
    - 3 shared cards with different levels
    - rng=None

    Expected:
    - Always returns card with highest weight (lowest level)
    """
    cards = [
        Card(id="g1", name="Gold1", category=CardCategory.GOLD_SHARED, level=1),
        Card(id="g2", name="Gold2", category=CardCategory.GOLD_SHARED, level=10),
        Card(id="g3", name="Gold3", category=CardCategory.GOLD_SHARED, level=50),
    ]

    game_state = GameState(
        day=1,
        cards=cards,
        coins=0,
        total_bluestars=0,
        streak_state=zero_streak,
    )

    for _ in range(10):
        selected = select_shared_card(game_state, base_config, zero_streak, rng=None)
        assert selected.id == "g1", (
            f"Deterministic mode should always pick level-1 card, got {selected.id}"
        )


def test_maxed_card_zero_duplicates(base_config):
    """
    Test 14 (Phase 2): Maxed cards receive zero duplicates.

    Setup:
    - Shared card at level 100 (max_shared_level)
    - Unique card at level 10 (max_unique_level)

    Expected:
    - compute_duplicates_received() returns 0
    """
    maxed_shared = Card(
        id="g1", name="Gold1", category=CardCategory.GOLD_SHARED, level=100
    )
    maxed_unique = Card(id="u1", name="Unique1", category=CardCategory.UNIQUE, level=10)

    assert compute_duplicates_received(maxed_shared, base_config, rng=None) == 0
    assert compute_duplicates_received(maxed_unique, base_config, rng=None) == 0


def test_duplicate_calculation_midpoint(base_config):
    """
    Test 15 (Phase 2): Deterministic mode uses percentile range midpoint.

    Setup:
    - Card at level 1 (index 0)
    - base cost = 10, min_pct = 0.8, max_pct = 1.2
    - rng=None

    Expected:
    - Returns round(10 * (0.8 + 1.2) / 2) = round(10) = 10
    """
    card = Card(id="g1", name="Gold1", category=CardCategory.GOLD_SHARED, level=1)

    duplicates = compute_duplicates_received(card, base_config, rng=None)

    expected = round(10 * (0.8 + 1.2) / 2.0)
    assert duplicates == expected, (
        f"Expected {expected} duplicates (midpoint), got {duplicates}"
    )


def test_full_pull_integration(base_config, zero_streak):
    """
    Test 16 (Phase 2): Full pull integration test.

    Setup:
    - GameState with 23 shared + 8 unique cards
    - Call perform_card_pull() with seeded RNG

    Expected:
    - Returns (Card, int>=0, int>=0, StreakState)
    - Selected card exists in game_state.cards
    - Streak state updated correctly
    - Duplicates and coins are non-negative
    """
    cards = []
    for i in range(12):
        cards.append(
            Card(
                id=f"g{i}",
                name=f"Gold{i}",
                category=CardCategory.GOLD_SHARED,
                level=1 + i,
            )
        )
    for i in range(11):
        cards.append(
            Card(
                id=f"b{i}",
                name=f"Blue{i}",
                category=CardCategory.BLUE_SHARED,
                level=1 + i,
            )
        )
    for i in range(8):
        cards.append(
            Card(id=f"u{i}", name=f"Unique{i}", category=CardCategory.UNIQUE, level=1)
        )

    game_state = GameState(
        day=1,
        cards=cards,
        coins=0,
        total_bluestars=0,
        streak_state=zero_streak,
    )

    rng = Random(42)
    selected_card, duplicates, coins, updated_streak = perform_card_pull(
        game_state, base_config, zero_streak, rng
    )

    assert selected_card in game_state.cards
    assert duplicates >= 0
    assert coins >= 0
    assert isinstance(updated_streak, StreakState)

    if selected_card.category in (CardCategory.GOLD_SHARED, CardCategory.BLUE_SHARED):
        assert updated_streak.streak_shared == 1
        assert updated_streak.streak_unique == 0
        assert selected_card.category.value in updated_streak.streak_per_color
    else:
        assert updated_streak.streak_unique == 1
        assert updated_streak.streak_shared == 0
        assert selected_card.id in updated_streak.streak_per_hero


def test_update_color_streak_gold(base_config, zero_streak):
    """
    Test 17 (Phase 2): Color streak update for Gold shared cards.

    Expected:
    - GOLD_SHARED streak increments
    - BLUE_SHARED streak resets to 0
    """
    cards = [
        Card(id="g1", name="Gold1", category=CardCategory.GOLD_SHARED, level=1),
        Card(id="b1", name="Blue1", category=CardCategory.BLUE_SHARED, level=1),
    ]
    game_state = GameState(
        day=1, cards=cards, coins=0, total_bluestars=0, streak_state=zero_streak
    )

    selected = cards[0]
    updated = update_card_streak(game_state, zero_streak, selected)

    assert updated.streak_per_color.get("GOLD_SHARED", 0) == 1
    assert updated.streak_per_color.get("BLUE_SHARED", 0) == 0


def test_update_color_streak_blue(base_config, zero_streak):
    """
    Test 18 (Phase 2): Color streak update for Blue shared cards.

    Expected:
    - BLUE_SHARED streak increments
    - GOLD_SHARED streak resets to 0
    """
    cards = [
        Card(id="g1", name="Gold1", category=CardCategory.GOLD_SHARED, level=1),
        Card(id="b1", name="Blue1", category=CardCategory.BLUE_SHARED, level=1),
    ]
    game_state = GameState(
        day=1, cards=cards, coins=0, total_bluestars=0, streak_state=zero_streak
    )

    streak_state = StreakState(
        streak_shared=0,
        streak_unique=0,
        streak_per_color={"GOLD_SHARED": 3, "BLUE_SHARED": 0},
        streak_per_hero={},
    )

    selected = cards[1]
    updated = update_card_streak(game_state, streak_state, selected)

    assert updated.streak_per_color.get("BLUE_SHARED", 0) == 1
    assert updated.streak_per_color.get("GOLD_SHARED", 0) == 0


def test_update_hero_streak_resets_others(base_config, zero_streak):
    """
    Test 19 (Phase 2): Hero streak update resets all other heroes.

    Expected:
    - Selected hero streak increments
    - All other hero streaks reset to 0
    """
    cards = [
        Card(id="u1", name="Unique1", category=CardCategory.UNIQUE, level=1),
        Card(id="u2", name="Unique2", category=CardCategory.UNIQUE, level=1),
        Card(id="u3", name="Unique3", category=CardCategory.UNIQUE, level=1),
    ]
    game_state = GameState(
        day=1, cards=cards, coins=0, total_bluestars=0, streak_state=zero_streak
    )

    streak_state = StreakState(
        streak_shared=0,
        streak_unique=0,
        streak_per_color={},
        streak_per_hero={"u1": 0, "u2": 5, "u3": 3},
    )

    selected = cards[0]
    updated = update_card_streak(game_state, streak_state, selected)

    assert updated.streak_per_hero.get("u1", 0) == 1
    assert updated.streak_per_hero.get("u2", 0) == 0
    assert updated.streak_per_hero.get("u3", 0) == 0
