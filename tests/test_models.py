"""
Tests for simulation models.

Verifies JSON serialization/deserialization, model validation, and default values.
"""

import json
import pytest

from simulation.models import (
    Card,
    CardCategory,
    CoinPerDuplicate,
    DuplicateRange,
    GameState,
    PackConfig,
    ProgressionMapping,
    SimConfig,
    SimResult,
    StreakState,
    UpgradeTable,
)


class TestCardCategory:
    """Test CardCategory enum."""

    def test_card_category_values(self):
        """Verify all card categories exist."""
        assert CardCategory.GOLD_SHARED.value == "GOLD_SHARED"
        assert CardCategory.BLUE_SHARED.value == "BLUE_SHARED"
        assert CardCategory.UNIQUE.value == "UNIQUE"


class TestCard:
    """Test Card model."""

    def test_card_defaults(self):
        """Test that Card defaults level=1 and duplicates=0."""
        card = Card(id="card_1", name="Test Card", category=CardCategory.GOLD_SHARED)
        assert card.level == 1
        assert card.duplicates == 0

    def test_card_with_explicit_values(self):
        """Test Card with explicit level and duplicates."""
        card = Card(
            id="card_2",
            name="Advanced Card",
            category=CardCategory.UNIQUE,
            level=5,
            duplicates=3,
        )
        assert card.level == 5
        assert card.duplicates == 3

    def test_card_json_serialization(self):
        """Test Card JSON round-trip serialization."""
        card = Card(
            id="card_3",
            name="Gold Shared",
            category=CardCategory.GOLD_SHARED,
            level=2,
            duplicates=1,
        )
        json_str = card.model_dump_json()
        deserialized = Card.model_validate_json(json_str)
        assert deserialized == card
        assert deserialized.id == "card_3"
        assert deserialized.level == 2
        assert deserialized.duplicates == 1

    def test_card_json_contains_all_fields(self):
        """Test that serialized JSON contains all fields."""
        card = Card(
            id="card_4",
            name="Test",
            category=CardCategory.BLUE_SHARED,
        )
        json_dict = json.loads(card.model_dump_json())
        assert "id" in json_dict
        assert "name" in json_dict
        assert "category" in json_dict
        assert "level" in json_dict
        assert "duplicates" in json_dict


class TestStreakState:
    """Test StreakState model."""

    def test_streak_state_basic(self):
        """Test basic StreakState creation."""
        streak = StreakState(
            streak_shared=5,
            streak_unique=2,
        )
        assert streak.streak_shared == 5
        assert streak.streak_unique == 2
        assert streak.streak_per_color == {}
        assert streak.streak_per_hero == {}

    def test_streak_state_with_dicts(self):
        """Test StreakState with populated dictionaries."""
        streak = StreakState(
            streak_shared=3,
            streak_unique=1,
            streak_per_color={"red": 2, "blue": 1},
            streak_per_hero={"hero_1": 5},
        )
        assert streak.streak_per_color == {"red": 2, "blue": 1}
        assert streak.streak_per_hero == {"hero_1": 5}

    def test_streak_state_json_serialization(self):
        """Test StreakState JSON round-trip serialization."""
        streak = StreakState(
            streak_shared=4,
            streak_unique=2,
            streak_per_color={"gold": 3},
            streak_per_hero={"hero_a": 10},
        )
        json_str = streak.model_dump_json()
        deserialized = StreakState.model_validate_json(json_str)
        assert deserialized == streak
        assert deserialized.streak_per_color == {"gold": 3}


class TestGameState:
    """Test GameState model."""

    def test_game_state_basic(self):
        """Test basic GameState creation."""
        streak = StreakState(streak_shared=0, streak_unique=0)
        state = GameState(
            day=1,
            coins=100,
            total_bluestars=0,
            streak_state=streak,
        )
        assert state.day == 1
        assert state.coins == 100
        assert state.total_bluestars == 0
        assert state.cards == []
        assert state.daily_log == []

    def test_game_state_with_cards(self):
        """Test GameState with cards."""
        card = Card(id="c1", name="Card 1", category=CardCategory.GOLD_SHARED)
        streak = StreakState(streak_shared=1, streak_unique=0)
        state = GameState(
            day=2,
            cards=[card],
            coins=50,
            total_bluestars=10,
            streak_state=streak,
        )
        assert len(state.cards) == 1
        assert state.cards[0].id == "c1"

    def test_game_state_json_serialization(self):
        """Test GameState JSON round-trip serialization."""
        card = Card(id="c2", name="Card 2", category=CardCategory.UNIQUE, level=3)
        streak = StreakState(streak_shared=2, streak_unique=1)
        state = GameState(
            day=5,
            cards=[card],
            coins=200,
            total_bluestars=25,
            streak_state=streak,
            unlock_schedule={"key": "value"},
            daily_log=[{"log": "entry"}],
        )
        json_str = state.model_dump_json()
        deserialized = GameState.model_validate_json(json_str)
        assert deserialized == state
        assert deserialized.day == 5
        assert len(deserialized.cards) == 1
        assert deserialized.daily_log == [{"log": "entry"}]


class TestPackConfig:
    """Test PackConfig model."""

    def test_pack_config_basic(self):
        """Test basic PackConfig creation."""
        pack = PackConfig(
            name="Standard Pack",
            card_types_table={1: 5, 2: 3, 3: 2},
        )
        assert pack.name == "Standard Pack"
        assert pack.card_types_table == {1: 5, 2: 3, 3: 2}

    def test_pack_config_json_serialization(self):
        """Test PackConfig JSON round-trip serialization."""
        pack = PackConfig(
            name="Premium Pack",
            card_types_table={1: 10, 2: 5},
        )
        json_str = pack.model_dump_json()
        deserialized = PackConfig.model_validate_json(json_str)
        assert deserialized == pack
        assert deserialized.name == "Premium Pack"


class TestUpgradeTable:
    """Test UpgradeTable model."""

    def test_upgrade_table_basic(self):
        """Test basic UpgradeTable creation."""
        table = UpgradeTable(
            category=CardCategory.GOLD_SHARED,
            duplicate_costs=[0, 10, 20, 30],
            coin_costs=[100, 200, 300],
            bluestar_rewards=[1, 2, 3],
        )
        assert table.category == CardCategory.GOLD_SHARED
        assert len(table.duplicate_costs) == 4

    def test_upgrade_table_json_serialization(self):
        """Test UpgradeTable JSON round-trip serialization."""
        table = UpgradeTable(
            category=CardCategory.UNIQUE,
            duplicate_costs=[0, 5, 10],
            coin_costs=[50, 100],
            bluestar_rewards=[10, 20],
        )
        json_str = table.model_dump_json()
        deserialized = UpgradeTable.model_validate_json(json_str)
        assert deserialized == table
        assert deserialized.category == CardCategory.UNIQUE


class TestDuplicateRange:
    """Test DuplicateRange model."""

    def test_duplicate_range_basic(self):
        """Test basic DuplicateRange creation."""
        dr = DuplicateRange(
            category=CardCategory.BLUE_SHARED,
            min_pct=[0.0, 0.1, 0.2],
            max_pct=[0.1, 0.2, 0.3],
        )
        assert dr.category == CardCategory.BLUE_SHARED
        assert len(dr.min_pct) == 3

    def test_duplicate_range_json_serialization(self):
        """Test DuplicateRange JSON round-trip serialization."""
        dr = DuplicateRange(
            category=CardCategory.GOLD_SHARED,
            min_pct=[0.0, 0.05],
            max_pct=[0.05, 0.15],
        )
        json_str = dr.model_dump_json()
        deserialized = DuplicateRange.model_validate_json(json_str)
        assert deserialized == dr


class TestCoinPerDuplicate:
    """Test CoinPerDuplicate model."""

    def test_coin_per_duplicate_basic(self):
        """Test basic CoinPerDuplicate creation."""
        cpd = CoinPerDuplicate(
            category=CardCategory.UNIQUE,
            coins_per_dupe=[5, 10, 15],
        )
        assert cpd.category == CardCategory.UNIQUE
        assert cpd.coins_per_dupe == [5, 10, 15]

    def test_coin_per_duplicate_json_serialization(self):
        """Test CoinPerDuplicate JSON round-trip serialization."""
        cpd = CoinPerDuplicate(
            category=CardCategory.BLUE_SHARED,
            coins_per_dupe=[2, 4, 6],
        )
        json_str = cpd.model_dump_json()
        deserialized = CoinPerDuplicate.model_validate_json(json_str)
        assert deserialized == cpd


class TestProgressionMapping:
    """Test ProgressionMapping model."""

    def test_progression_mapping_basic(self):
        """Test basic ProgressionMapping creation."""
        pm = ProgressionMapping(
            shared_levels=[1, 2, 3, 4, 5],
            unique_levels=[1, 2, 3],
        )
        assert len(pm.shared_levels) == 5
        assert len(pm.unique_levels) == 3

    def test_progression_mapping_json_serialization(self):
        """Test ProgressionMapping JSON round-trip serialization."""
        pm = ProgressionMapping(
            shared_levels=[10, 20, 30],
            unique_levels=[100, 200],
        )
        json_str = pm.model_dump_json()
        deserialized = ProgressionMapping.model_validate_json(json_str)
        assert deserialized == pm


class TestSimConfig:
    """Test SimConfig model."""

    def test_sim_config_defaults(self):
        """Test SimConfig default values."""
        pm = ProgressionMapping(shared_levels=[1, 2], unique_levels=[1])
        config = SimConfig(
            packs=[],
            upgrade_tables={},
            duplicate_ranges={},
            coin_per_duplicate={},
            progression_mapping=pm,
            unique_unlock_schedule={},
            pack_averages={},
            num_days=30,
        )
        assert config.base_shared_rate == 0.70
        assert config.base_unique_rate == 0.30
        assert config.max_shared_level == 100
        assert config.max_unique_level == 10
        assert config.mc_runs is None

    def test_sim_config_with_custom_values(self):
        """Test SimConfig with custom values."""
        pack = PackConfig(name="Test Pack", card_types_table={1: 5})
        pm = ProgressionMapping(shared_levels=[1], unique_levels=[1])
        config = SimConfig(
            packs=[pack],
            upgrade_tables={},
            duplicate_ranges={},
            coin_per_duplicate={},
            progression_mapping=pm,
            unique_unlock_schedule={1: 5},
            pack_averages={"test": 1.5},
            num_days=60,
            mc_runs=1000,
            base_shared_rate=0.60,
            base_unique_rate=0.40,
            max_shared_level=150,
            max_unique_level=20,
        )
        assert config.mc_runs == 1000
        assert config.base_shared_rate == 0.60
        assert config.max_unique_level == 20

    def test_sim_config_json_serialization(self):
        """Test SimConfig JSON round-trip serialization."""
        pack = PackConfig(name="Pack1", card_types_table={1: 3})
        table = UpgradeTable(
            category=CardCategory.GOLD_SHARED,
            duplicate_costs=[0, 5],
            coin_costs=[100],
            bluestar_rewards=[1],
        )
        pm = ProgressionMapping(shared_levels=[1, 2], unique_levels=[1])
        config = SimConfig(
            packs=[pack],
            upgrade_tables={CardCategory.GOLD_SHARED: table},
            duplicate_ranges={},
            coin_per_duplicate={},
            progression_mapping=pm,
            unique_unlock_schedule={},
            pack_averages={},
            num_days=45,
            mc_runs=500,
        )
        json_str = config.model_dump_json()
        deserialized = SimConfig.model_validate_json(json_str)
        assert deserialized == config
        assert len(deserialized.packs) == 1
        assert deserialized.num_days == 45


class TestSimResult:
    """Test SimResult model."""

    def test_sim_result_basic(self):
        """Test basic SimResult creation."""
        result = SimResult(
            total_bluestars=100,
            total_coins_earned=5000,
            total_coins_spent=3000,
        )
        assert result.total_bluestars == 100
        assert result.total_coins_earned == 5000
        assert result.total_coins_spent == 3000
        assert result.daily_snapshots == []
        assert result.total_upgrades == {}

    def test_sim_result_with_data(self):
        """Test SimResult with snapshots and upgrade data."""
        result = SimResult(
            daily_snapshots=[{"day": 1, "coins": 100}],
            total_bluestars=50,
            total_coins_earned=2000,
            total_coins_spent=1000,
            total_upgrades={"shared": 10, "unique": 5},
        )
        assert len(result.daily_snapshots) == 1
        assert result.total_upgrades == {"shared": 10, "unique": 5}

    def test_sim_result_json_serialization(self):
        """Test SimResult JSON round-trip serialization."""
        result = SimResult(
            daily_snapshots=[{"day": 1}, {"day": 2}],
            total_bluestars=75,
            total_coins_earned=3000,
            total_coins_spent=2000,
            total_upgrades={"gold": 15},
        )
        json_str = result.model_dump_json()
        deserialized = SimResult.model_validate_json(json_str)
        assert deserialized == result
        assert len(deserialized.daily_snapshots) == 2


class TestIntegration:
    """Integration tests for complex model interactions."""

    def test_complex_game_state_serialization(self):
        """Test serialization of complex nested GameState."""
        cards = [
            Card(
                id="c1",
                name="Card 1",
                category=CardCategory.GOLD_SHARED,
                level=5,
                duplicates=2,
            ),
            Card(
                id="c2",
                name="Card 2",
                category=CardCategory.UNIQUE,
                level=3,
                duplicates=0,
            ),
        ]
        streak = StreakState(
            streak_shared=3,
            streak_unique=1,
            streak_per_color={"gold": 2, "blue": 1},
            streak_per_hero={"hero_a": 5},
        )
        state = GameState(
            day=10,
            cards=cards,
            coins=500,
            total_bluestars=50,
            streak_state=streak,
            unlock_schedule={"hero_a": 1, "hero_b": 2},
            daily_log=[{"day": 1, "event": "pack_opened"}],
        )
        json_str = state.model_dump_json()
        deserialized = GameState.model_validate_json(json_str)
        assert deserialized == state
        assert len(deserialized.cards) == 2
        assert deserialized.cards[0].level == 5
        assert deserialized.streak_state.streak_per_color == {"gold": 2, "blue": 1}
        assert deserialized.daily_log[0]["event"] == "pack_opened"

    def test_full_sim_config_serialization(self):
        """Test serialization of complete SimConfig."""
        packs = [
            PackConfig(name="Basic", card_types_table={1: 5, 2: 3}),
            PackConfig(name="Premium", card_types_table={2: 5, 3: 5}),
        ]
        upgrade_tables = {
            CardCategory.GOLD_SHARED: UpgradeTable(
                category=CardCategory.GOLD_SHARED,
                duplicate_costs=[0, 10, 20],
                coin_costs=[100, 200],
                bluestar_rewards=[1, 2],
            ),
            CardCategory.UNIQUE: UpgradeTable(
                category=CardCategory.UNIQUE,
                duplicate_costs=[0, 5],
                coin_costs=[500],
                bluestar_rewards=[10],
            ),
        }
        pm = ProgressionMapping(
            shared_levels=[1, 2, 3, 4, 5],
            unique_levels=[1, 2],
        )
        config = SimConfig(
            packs=packs,
            upgrade_tables=upgrade_tables,
            duplicate_ranges={},
            coin_per_duplicate={},
            progression_mapping=pm,
            unique_unlock_schedule={1: 1, 2: 2},
            pack_averages={"basic": 0.5, "premium": 0.8},
            num_days=30,
            mc_runs=100,
        )
        json_str = config.model_dump_json()
        deserialized = SimConfig.model_validate_json(json_str)
        assert deserialized == config
        assert len(deserialized.packs) == 2
        assert len(deserialized.upgrade_tables) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
