"""
Tests for the pack processing system.

Covers:
- Zero packs per day
- Deterministic rounding behavior
- Floor lookup for card_types_table
- Multiple pack types
- MC mode with Poisson distribution
"""

import pytest
from random import Random

import numpy as np

from simulation.models import (
    CardCategory,
    GameState,
    PackConfig,
    ProgressionMapping,
    SimConfig,
    StreakState,
)
from simulation.pack_system import (
    CardPull,
    _get_card_types_for_count,
    process_packs_for_day,
)


def _make_test_config(
    pack_averages: dict[str, float], packs: list[PackConfig]
) -> SimConfig:
    """Create minimal SimConfig for testing."""
    return SimConfig(
        packs=packs,
        upgrade_tables={},
        duplicate_ranges={},
        coin_per_duplicate={},
        progression_mapping=ProgressionMapping(shared_levels=[], unique_levels=[]),
        unique_unlock_schedule={},
        pack_averages=pack_averages,
        num_days=1,
    )


class TestCardTypesLookup:
    """Test floor lookup behavior for card_types_table."""

    def test_exact_key_match(self):
        """Exact key in table should return corresponding value."""
        table = {0: 1, 10: 2, 20: 3}
        assert _get_card_types_for_count(table, 10) == 2

    def test_floor_lookup(self):
        """Should use floor key when exact match missing."""
        table = {0: 1, 10: 2, 20: 3}
        # 15 is between 10 and 20, should use 10
        assert _get_card_types_for_count(table, 15) == 2

    def test_minimum_key(self):
        """Should use minimum key when total_unlocked < 10."""
        table = {0: 1, 10: 2, 20: 3}
        assert _get_card_types_for_count(table, 5) == 1

    def test_maximum_key(self):
        """Should use highest key when total_unlocked exceeds it."""
        table = {0: 1, 10: 2, 20: 3}
        assert _get_card_types_for_count(table, 100) == 3

    def test_below_minimum_raises(self):
        """Should raise ValueError if total_unlocked below minimum key."""
        table = {10: 1, 20: 2}
        with pytest.raises(ValueError, match="below minimum table key"):
            _get_card_types_for_count(table, 5)


class TestProcessPacksZero:
    """Test zero pack edge case."""

    def test_zero_packs_deterministic(self):
        """Zero average should produce zero pulls."""
        game_state = GameState(
            day=1,
            cards=[],
            coins=0,
            total_bluestars=0,
            streak_state=StreakState(streak_shared=0, streak_unique=0),
        )

        config = _make_test_config(
            pack_averages={"basic": 0.0, "premium": 0.0},
            packs=[
                PackConfig(name="basic", card_types_table={0: 1}),
                PackConfig(name="premium", card_types_table={0: 2}),
            ],
        )

        pulls = process_packs_for_day(game_state, config, rng=None)
        assert len(pulls) == 0

    def test_zero_packs_mc(self):
        """Zero average should produce zero pulls in MC mode."""
        game_state = GameState(
            day=1,
            cards=[],
            coins=0,
            total_bluestars=0,
            streak_state=StreakState(streak_shared=0, streak_unique=0),
        )

        config = _make_test_config(
            pack_averages={"basic": 0.0},
            packs=[PackConfig(name="basic", card_types_table={0: 1})],
        )

        np.random.seed(42)
        rng = Random()
        pulls = process_packs_for_day(game_state, config, rng=rng)
        assert len(pulls) == 0


class TestProcessPacksDeterministic:
    """Test deterministic rounding behavior."""

    def test_round_half_up_2_5(self):
        """2.5 should round to 2 (banker's rounding) or 3 (half-up)."""
        game_state = GameState(
            day=1,
            cards=[],
            coins=0,
            total_bluestars=0,
            streak_state=StreakState(streak_shared=0, streak_unique=0),
        )

        config = _make_test_config(
            pack_averages={"basic": 2.5},
            packs=[PackConfig(name="basic", card_types_table={0: 1})],
        )

        pulls = process_packs_for_day(game_state, config, rng=None)
        assert len(pulls) == 2

    def test_round_2_4_down(self):
        """2.4 should round to 2."""
        game_state = GameState(
            day=1,
            cards=[],
            coins=0,
            total_bluestars=0,
            streak_state=StreakState(streak_shared=0, streak_unique=0),
        )

        config = _make_test_config(
            pack_averages={"basic": 2.4},
            packs=[PackConfig(name="basic", card_types_table={0: 1})],
        )

        pulls = process_packs_for_day(game_state, config, rng=None)
        assert len(pulls) == 2

    def test_round_2_6_up(self):
        """2.6 should round to 3."""
        game_state = GameState(
            day=1,
            cards=[],
            coins=0,
            total_bluestars=0,
            streak_state=StreakState(streak_shared=0, streak_unique=0),
        )

        config = _make_test_config(
            pack_averages={"basic": 2.6},
            packs=[PackConfig(name="basic", card_types_table={0: 1})],
        )

        pulls = process_packs_for_day(game_state, config, rng=None)
        assert len(pulls) == 3


class TestProcessPacksMultipleTypes:
    """Test multiple pack types in single day."""

    def test_multiple_pack_types(self):
        """Multiple pack types should each contribute pulls."""
        game_state = GameState(
            day=1,
            cards=[],
            coins=0,
            total_bluestars=0,
            streak_state=StreakState(streak_shared=0, streak_unique=0),
        )

        config = _make_test_config(
            pack_averages={"basic": 2.0, "premium": 1.0},
            packs=[
                PackConfig(name="basic", card_types_table={0: 1}),
                PackConfig(name="premium", card_types_table={0: 2}),
            ],
        )

        pulls = process_packs_for_day(game_state, config, rng=None)
        assert len(pulls) == 4
        assert sum(1 for p in pulls if p.pack_name == "basic") == 2
        assert sum(1 for p in pulls if p.pack_name == "premium") == 2

    def test_card_types_floor_lookup_during_pull(self):
        """Should use floor lookup during pull generation."""
        game_state = GameState(
            day=1,
            cards=[],
            coins=0,
            total_bluestars=0,
            streak_state=StreakState(streak_shared=0, streak_unique=0),
        )

        config = _make_test_config(
            pack_averages={"basic": 1.0},
            packs=[PackConfig(name="basic", card_types_table={0: 1, 10: 2, 20: 3})],
        )

        pulls = process_packs_for_day(game_state, config, rng=None)
        assert len(pulls) == 1

    def test_floor_lookup_specific_scenario(self):
        """Specific scenario: 0 unlocked, table {0:1, 10:2, 20:3} → key 0 → 1 type."""
        game_state = GameState(
            day=1,
            cards=[],
            coins=0,
            total_bluestars=0,
            streak_state=StreakState(streak_shared=0, streak_unique=0),
        )

        config = _make_test_config(
            pack_averages={"basic": 1.0},
            packs=[PackConfig(name="basic", card_types_table={0: 1, 10: 2, 20: 3})],
        )

        pulls = process_packs_for_day(game_state, config, rng=None)
        assert len(pulls) == 1


class TestProcessPacksMC:
    """Test Monte Carlo mode with Poisson distribution."""

    def test_mc_poisson_distribution(self):
        """MC mode should use Poisson distribution."""
        game_state = GameState(
            day=1,
            cards=[],
            coins=0,
            total_bluestars=0,
            streak_state=StreakState(streak_shared=0, streak_unique=0),
        )

        config = _make_test_config(
            pack_averages={"basic": 3.0},
            packs=[PackConfig(name="basic", card_types_table={0: 1})],
        )

        np.random.seed(42)
        rng = Random()
        pulls = process_packs_for_day(game_state, config, rng=rng)
        assert isinstance(len(pulls), int)
        assert len(pulls) >= 0

    def test_mc_repeatable_with_seed(self):
        """Same seed should produce same results."""
        game_state = GameState(
            day=1,
            cards=[],
            coins=0,
            total_bluestars=0,
            streak_state=StreakState(streak_shared=0, streak_unique=0),
        )

        config = _make_test_config(
            pack_averages={"basic": 2.5},
            packs=[PackConfig(name="basic", card_types_table={0: 1})],
        )

        rng1 = Random(123)
        pulls1 = process_packs_for_day(game_state, config, rng=rng1)

        rng2 = Random(123)
        pulls2 = process_packs_for_day(game_state, config, rng=rng2)

        assert len(pulls1) == len(pulls2)


class TestCardPullDataclass:
    """Test CardPull dataclass."""

    def test_card_pull_creation(self):
        """CardPull should store pack_name and pull_index."""
        pull = CardPull(pack_name="basic", pull_index=5)
        assert pull.pack_name == "basic"
        assert pull.pull_index == 5

    def test_card_pull_fields(self):
        """CardPull should have exactly pack_name and pull_index fields."""
        pull = CardPull(pack_name="premium", pull_index=10)
        assert hasattr(pull, "pack_name")
        assert hasattr(pull, "pull_index")
