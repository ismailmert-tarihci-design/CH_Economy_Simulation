"""
Tests for configuration loader.

Verifies that load_defaults() properly loads all JSON files and
returns a valid SimConfig object.
"""

import pytest
from pathlib import Path

from simulation.config_loader import load_defaults
from simulation.models import SimConfig, CardCategory


class TestConfigLoader:
    """Test suite for config_loader module."""

    def test_load_defaults_returns_simconfig(self):
        """load_defaults() should return SimConfig instance."""
        config = load_defaults()
        assert isinstance(config, SimConfig)

    def test_load_defaults_has_nine_packs(self):
        """SimConfig should contain 9 packs."""
        config = load_defaults()
        assert len(config.packs) == 9
        pack_names = [p.name for p in config.packs]
        assert pack_names == [
            "Pack1",
            "Pack2",
            "Pack3",
            "Pack4",
            "Pack5",
            "Pack6",
            "Pack7",
            "Pack8",
            "Pack9",
        ]

    def test_load_defaults_has_three_upgrade_tables(self):
        """SimConfig should contain 3 upgrade table categories."""
        config = load_defaults()
        assert len(config.upgrade_tables) == 3
        categories = set(config.upgrade_tables.keys())
        expected = {
            CardCategory.GOLD_SHARED,
            CardCategory.BLUE_SHARED,
            CardCategory.UNIQUE,
        }
        assert categories == expected

    def test_upgrade_tables_have_correct_lengths(self):
        """Upgrade tables should have 99 levels for shared, 9 for unique."""
        config = load_defaults()

        # Shared categories: 99 levels
        shared_length = len(
            config.upgrade_tables[CardCategory.GOLD_SHARED].duplicate_costs
        )
        assert shared_length == 99
        assert (
            len(config.upgrade_tables[CardCategory.BLUE_SHARED].duplicate_costs) == 99
        )

        # Unique category: 9 levels
        unique_length = len(config.upgrade_tables[CardCategory.UNIQUE].duplicate_costs)
        assert unique_length == 9

    def test_duplicate_ranges_structure(self):
        """Duplicate ranges should have min/max arrays matching upgrade tables."""
        config = load_defaults()

        for category, dup_range in config.duplicate_ranges.items():
            upgrade_table = config.upgrade_tables[category]
            expected_length = len(upgrade_table.duplicate_costs)
            assert len(dup_range.min_pct) == expected_length
            assert len(dup_range.max_pct) == expected_length

    def test_coin_per_duplicate_structure(self):
        """Coin per duplicate should match upgrade table lengths."""
        config = load_defaults()

        for category, coin_dupe in config.coin_per_duplicate.items():
            upgrade_table = config.upgrade_tables[category]
            expected_length = len(upgrade_table.duplicate_costs)
            assert len(coin_dupe.coins_per_dupe) == expected_length

    def test_progression_mapping_contains_expected_keys(self):
        """Progression mapping should contain exact mapping from spec."""
        config = load_defaults()
        mapping = config.progression_mapping

        # Expected shared levels from task spec
        expected_shared = [1, 5, 10, 15, 25, 45, 60, 70, 80, 90, 100]
        expected_unique = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 10]

        assert mapping.shared_levels == expected_shared
        assert mapping.unique_levels == expected_unique

    def test_unique_unlock_schedule_is_dict(self):
        """Unique unlock schedule should be proper dict with integer keys."""
        config = load_defaults()
        schedule = config.unique_unlock_schedule

        assert isinstance(schedule, dict)
        assert 1 in schedule
        assert schedule[1] == 8
        assert schedule[30] == 1
        assert schedule[60] == 1
        assert schedule[90] == 1

    def test_pack_averages_has_nine_entries(self):
        """Pack averages should have 9 entries."""
        config = load_defaults()
        pack_avg = config.pack_averages

        assert len(pack_avg) == 9
        pack_names = set(pack_avg.keys())
        expected_names = {f"Pack{i}" for i in range(1, 10)}
        assert pack_names == expected_names

    def test_all_required_fields_populated(self):
        """SimConfig should have all required fields populated."""
        config = load_defaults()

        assert config.packs is not None
        assert config.upgrade_tables is not None
        assert config.duplicate_ranges is not None
        assert config.coin_per_duplicate is not None
        assert config.progression_mapping is not None
        assert config.unique_unlock_schedule is not None
        assert config.pack_averages is not None
        assert config.num_days > 0

    def test_pack_card_types_table_structure(self):
        """Each pack should have card_types_table with expected structure."""
        config = load_defaults()

        for pack in config.packs:
            assert isinstance(pack.card_types_table, dict)
            assert 31 in pack.card_types_table
            assert 40 in pack.card_types_table
            assert 50 in pack.card_types_table
            assert pack.card_types_table[31] == 3
            assert pack.card_types_table[40] == 4
            assert pack.card_types_table[50] == 5
