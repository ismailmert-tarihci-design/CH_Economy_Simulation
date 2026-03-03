import pytest
import importlib

from simulation.models import (
    CardCategory,
    CardTypesRange,
    CoinPerDuplicate,
    DuplicateRange,
    GameState,
    GearDesignConfig,
    GearDesignIncomeRow,
    GearSlotCostConfig,
    GearSlotCostRow,
    GearSystemConfig,
    PackConfig,
    ProgressionMapping,
    SimConfig,
    StreakState,
    UpgradeTable,
)


def _config_with_gear() -> SimConfig:
    shared_upgrade = UpgradeTable(
        category=CardCategory.GOLD_SHARED,
        duplicate_costs=[1] * 100,
        coin_costs=[1] * 100,
        bluestar_rewards=[1] * 100,
    )
    unique_upgrade = UpgradeTable(
        category=CardCategory.UNIQUE,
        duplicate_costs=[1] * 10,
        coin_costs=[1] * 10,
        bluestar_rewards=[1] * 10,
    )

    cost_rows = [
        GearSlotCostRow(slot_id=slot_id, level=level, design_cost=1)
        for slot_id in range(1, 7)
        for level in range(2, 101)
    ]

    return SimConfig(
        packs=[
            PackConfig(name="dummy", card_types_table={0: CardTypesRange(min=1, max=1)})
        ],
        upgrade_tables={
            CardCategory.GOLD_SHARED: shared_upgrade,
            CardCategory.BLUE_SHARED: shared_upgrade,
            CardCategory.UNIQUE: unique_upgrade,
        },
        duplicate_ranges={
            CardCategory.GOLD_SHARED: DuplicateRange(
                category=CardCategory.GOLD_SHARED,
                min_pct=[1.0] * 100,
                max_pct=[1.0] * 100,
            ),
            CardCategory.BLUE_SHARED: DuplicateRange(
                category=CardCategory.BLUE_SHARED,
                min_pct=[1.0] * 100,
                max_pct=[1.0] * 100,
            ),
            CardCategory.UNIQUE: DuplicateRange(
                category=CardCategory.UNIQUE,
                min_pct=[1.0] * 10,
                max_pct=[1.0] * 10,
            ),
        },
        coin_per_duplicate={
            CardCategory.GOLD_SHARED: CoinPerDuplicate(
                category=CardCategory.GOLD_SHARED,
                coins_per_dupe=[1] * 100,
            ),
            CardCategory.BLUE_SHARED: CoinPerDuplicate(
                category=CardCategory.BLUE_SHARED,
                coins_per_dupe=[1] * 100,
            ),
            CardCategory.UNIQUE: CoinPerDuplicate(
                category=CardCategory.UNIQUE,
                coins_per_dupe=[1] * 10,
            ),
        },
        progression_mapping=ProgressionMapping(shared_levels=[1], unique_levels=[1]),
        unique_unlock_schedule={1: 1},
        daily_pack_schedule=[{"dummy": 1.0}],
        num_days=1,
        gear_system_config=GearSystemConfig(
            design_income=GearDesignConfig(
                income_table=[
                    GearDesignIncomeRow(day_start=1, day_end=10, designs_per_day=8)
                ]
            ),
            slot_costs=GearSlotCostConfig(cost_table=cost_rows),
        ),
    )


def _state(day: int) -> GameState:
    return GameState(
        day=day,
        cards=[],
        coins=0,
        total_bluestars=0,
        streak_state=StreakState(
            streak_shared=0,
            streak_unique=0,
            streak_per_color={},
            streak_per_hero={},
        ),
    )


def test_allocate_designs_even_split():
    module = importlib.import_module("simulation.gear_system")
    allocation = module.allocate_designs(12, day=1)
    assert allocation == {1: 2, 2: 2, 3: 2, 4: 2, 5: 2, 6: 2}


def test_allocate_designs_rotating_remainder():
    module = importlib.import_module("simulation.gear_system")
    day1 = module.allocate_designs(8, day=1)
    day2 = module.allocate_designs(8, day=2)
    day3 = module.allocate_designs(8, day=3)

    assert day1 == {1: 2, 2: 2, 3: 1, 4: 1, 5: 1, 6: 1}
    assert day2 == {1: 1, 2: 2, 3: 2, 4: 1, 5: 1, 6: 1}
    assert day3 == {1: 1, 2: 1, 3: 2, 4: 2, 5: 1, 6: 1}


def test_allocate_designs_rejects_negative():
    module = importlib.import_module("simulation.gear_system")
    with pytest.raises(ValueError, match="designs_income must be non-negative"):
        module.allocate_designs(-1, day=1)


def test_attempt_gear_upgrades_consumes_budget_and_caps_levels():
    module = importlib.import_module("simulation.gear_system")
    config = _config_with_gear()
    state = _state(day=1)

    events = module.attempt_gear_upgrades(
        state, config, daily_design_allocation={1: 3, 2: 1}
    )

    assert state.gear_state is not None
    assert state.gear_state.slot_levels[1] == 4
    assert state.gear_state.slot_levels[2] == 2
    assert len(events) == 4


def test_attempt_gear_upgrades_missing_cost_entry_fails_fast():
    module = importlib.import_module("simulation.gear_system")
    config = _config_with_gear()
    assert config.gear_system_config is not None
    assert config.gear_system_config.slot_costs is not None
    config.gear_system_config.slot_costs.cost_table = [
        row
        for row in config.gear_system_config.slot_costs.cost_table
        if not (row.slot_id == 1 and row.level == 2)
    ]
    state = _state(day=1)

    with pytest.raises(ValueError, match="Missing gear level-cost entry"):
        module.attempt_gear_upgrades(state, config, daily_design_allocation={1: 1})
