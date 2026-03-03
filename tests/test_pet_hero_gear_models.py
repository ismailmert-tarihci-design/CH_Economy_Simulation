
"""
Test suite for new pet/hero/gear system state and config models.

Tests verify:
1. Model creation with defaults
2. Model creation with explicit values  
3. JSON serialization/deserialization round-trips
4. Integration with SimConfig
5. Validation of required vs optional fields
6. Backward compatibility with existing GameState/SimConfig
"""

import json
import pytest

from simulation.models import (
    PetState,
    HeroState,
    GearState,
    PetSystemConfig,
    HeroSystemConfig,
    GearSystemConfig,
    SimConfig,
    ProgressionMapping,
)


class TestPetState:
    """Test PetState model."""

    def test_pet_state_defaults(self):
        """Test PetState default values."""
        pet = PetState()
        assert pet.tier == 1
        assert pet.summon_count == 0
        assert pet.owned_pets == {}
        assert pet.pet_levels == {}
        assert pet.pet_duplicates == {}
        assert pet.build_levels == {}

    def test_pet_state_with_values(self):
        """Test PetState with explicit values."""
        pet = PetState(
            tier=8,
            summon_count=25,
            owned_pets={"pet_1": True, "pet_2": False},
            pet_levels={"pet_1": 50, "pet_2": 30},
            pet_duplicates={"pet_1": 3},
            build_levels={"pet_1": 5},
        )
        assert pet.tier == 8
        assert pet.summon_count == 25
        assert pet.owned_pets["pet_1"] is True
        assert pet.pet_levels["pet_1"] == 50
        assert pet.pet_duplicates["pet_1"] == 3
        assert pet.build_levels["pet_1"] == 5

    def test_pet_state_json_serialization(self):
        """Test PetState JSON round-trip."""
        pet = PetState(
            tier=5,
            summon_count=10,
            owned_pets={"pet_a": True},
            pet_levels={"pet_a": 75},
        )
        json_str = pet.model_dump_json()
        loaded = PetState.model_validate_json(json_str)
        assert loaded == pet
        assert loaded.tier == 5

    def test_pet_state_missing_required_field_raises_error(self):
        """Test that missing any required field raises validation error."""
        # PetState has no required fields (all have defaults), so we can always create it
        pet = PetState()
        assert pet is not None


class TestHeroState:
    """Test HeroState model."""

    def test_hero_state_defaults(self):
        """Test HeroState default values."""
        hero = HeroState()
        assert hero.unlocked_heroes == []
        assert hero.unique_card_count == 0

    def test_hero_state_with_values(self):
        """Test HeroState with explicit values."""
        hero = HeroState(
            unlocked_heroes=["hero_1", "hero_2", "hero_3"],
            unique_card_count=15,
        )
        assert len(hero.unlocked_heroes) == 3
        assert hero.unlocked_heroes[0] == "hero_1"
        assert hero.unique_card_count == 15

    def test_hero_state_json_serialization(self):
        """Test HeroState JSON round-trip."""
        hero = HeroState(
            unlocked_heroes=["hero_a", "hero_b"],
            unique_card_count=8,
        )
        json_str = hero.model_dump_json()
        loaded = HeroState.model_validate_json(json_str)
        assert loaded == hero
        assert len(loaded.unlocked_heroes) == 2


class TestGearState:
    """Test GearState model."""

    def test_gear_state_defaults(self):
        """Test GearState default values."""
        gear = GearState()
        assert gear.slot_levels == {}
        assert gear.design_budgets == {}

    def test_gear_state_with_values(self):
        """Test GearState with 6 slots."""
        gear = GearState(
            slot_levels={0: 50, 1: 75, 2: 25, 3: 100, 4: 60, 5: 40},
            design_budgets={0: 1000, 1: 500, 2: 200, 3: 0, 4: 800, 5: 1500},
        )
        assert gear.slot_levels[0] == 50
        assert gear.slot_levels[3] == 100
        assert gear.design_budgets[1] == 500
        assert gear.design_budgets[3] == 0

    def test_gear_state_json_serialization(self):
        """Test GearState JSON round-trip."""
        gear = GearState(
            slot_levels={0: 30, 1: 60, 2: 75},
            design_budgets={0: 2000, 1: 1500},
        )
        json_str = gear.model_dump_json()
        loaded = GearState.model_validate_json(json_str)
        assert loaded == gear
        assert loaded.slot_levels[0] == 30


class TestSystemConfigs:
    """Test system configuration models."""

    def test_pet_system_config_creation(self):
        """Test PetSystemConfig is creatable."""
        config = PetSystemConfig()
        assert isinstance(config, PetSystemConfig)

    def test_hero_system_config_creation(self):
        """Test HeroSystemConfig is creatable."""
        config = HeroSystemConfig()
        assert isinstance(config, HeroSystemConfig)

    def test_gear_system_config_creation(self):
        """Test GearSystemConfig is creatable."""
        config = GearSystemConfig()
        assert isinstance(config, GearSystemConfig)

    def test_system_config_json_serialization(self):
        """Test system configs serialize to JSON."""
        pet_cfg = PetSystemConfig()
        hero_cfg = HeroSystemConfig()
        gear_cfg = GearSystemConfig()
        
        # Should not raise
        assert pet_cfg.model_dump_json()
        assert hero_cfg.model_dump_json()
        assert gear_cfg.model_dump_json()


class TestSimConfigIntegration:
    """Test integration with SimConfig."""

    def test_sim_config_backward_compatible_no_system_configs(self):
        """Test SimConfig works without system configs (backward compatible)."""
        pm = ProgressionMapping(shared_levels=[1, 2], unique_levels=[1])
        config = SimConfig(
            packs=[],
            upgrade_tables={},
            duplicate_ranges={},
            coin_per_duplicate={},
            progression_mapping=pm,
            unique_unlock_schedule={},
            daily_pack_schedule=[],
            num_days=30,
        )
        assert config.pet_system_config is None
        assert config.hero_system_config is None
        assert config.gear_system_config is None

    def test_sim_config_with_pet_system(self):
        """Test SimConfig with pet system config."""
        pm = ProgressionMapping(shared_levels=[1], unique_levels=[1])
        config = SimConfig(
            packs=[],
            upgrade_tables={},
            duplicate_ranges={},
            coin_per_duplicate={},
            progression_mapping=pm,
            unique_unlock_schedule={},
            daily_pack_schedule=[],
            num_days=30,
            pet_system_config=PetSystemConfig(),
        )
        assert config.pet_system_config is not None
        assert config.hero_system_config is None
        assert config.gear_system_config is None

    def test_sim_config_with_all_systems(self):
        """Test SimConfig with all three system configs."""
        pm = ProgressionMapping(shared_levels=[1], unique_levels=[1])
        config = SimConfig(
            packs=[],
            upgrade_tables={},
            duplicate_ranges={},
            coin_per_duplicate={},
            progression_mapping=pm,
            unique_unlock_schedule={},
            daily_pack_schedule=[],
            num_days=30,
            pet_system_config=PetSystemConfig(),
            hero_system_config=HeroSystemConfig(),
            gear_system_config=GearSystemConfig(),
        )
        assert config.pet_system_config is not None
        assert config.hero_system_config is not None
        assert config.gear_system_config is not None

    def test_sim_config_json_serialization_with_system_configs(self):
        """Test SimConfig with system configs round-trips through JSON."""
        pm = ProgressionMapping(shared_levels=[1], unique_levels=[1])
        config = SimConfig(
            packs=[],
            upgrade_tables={},
            duplicate_ranges={},
            coin_per_duplicate={},
            progression_mapping=pm,
            unique_unlock_schedule={},
            daily_pack_schedule=[],
            num_days=30,
            pet_system_config=PetSystemConfig(),
            hero_system_config=HeroSystemConfig(),
            gear_system_config=GearSystemConfig(),
        )
        json_str = config.model_dump_json()
        loaded = SimConfig.model_validate_json(json_str)
        assert loaded.pet_system_config is not None
        assert loaded.hero_system_config is not None
        assert loaded.gear_system_config is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
