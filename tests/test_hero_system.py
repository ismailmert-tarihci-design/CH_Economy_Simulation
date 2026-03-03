import importlib
from simulation.models import (
    CardCategory,
    CardTypesRange,
    CoinPerDuplicate,
    DuplicateRange,
    GameState,
    HeroSystemConfig,
    HeroUnlockRow,
    PackConfig,
    ProgressionMapping,
    SimConfig,
    StreakState,
    UpgradeTable,
)


def _base_config(unlock_rows: list[HeroUnlockRow]) -> SimConfig:
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
        hero_system_config=HeroSystemConfig(unlock_rows=unlock_rows),
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


def test_process_hero_unlocks_aggregates_same_day_rows():
    module = importlib.import_module("simulation.hero_system")
    config = _base_config(
        unlock_rows=[
            HeroUnlockRow(day=5, hero_id="hero_a", unique_cards_added=2),
            HeroUnlockRow(day=5, hero_id="hero_a", unique_cards_added=3),
            HeroUnlockRow(day=5, hero_id="hero_b", unique_cards_added=4),
        ]
    )
    state = _state(day=5)

    events = module.process_hero_unlocks(state, config, day=5)

    assert [event.hero_id for event in events] == ["hero_a", "hero_b"]
    assert [event.unique_cards_added for event in events] == [5, 4]
    assert state.hero_state is not None
    assert state.hero_state.unique_card_count == 9


def test_process_hero_unlocks_returns_empty_without_rows():
    module = importlib.import_module("simulation.hero_system")
    config = _base_config(unlock_rows=[])
    state = _state(day=2)

    events = module.process_hero_unlocks(state, config, day=2)

    assert events == []


def test_process_hero_unlocks_is_day_scoped():
    module = importlib.import_module("simulation.hero_system")
    config = _base_config(
        unlock_rows=[
            HeroUnlockRow(day=1, hero_id="hero_a", unique_cards_added=1),
            HeroUnlockRow(day=3, hero_id="hero_b", unique_cards_added=2),
        ]
    )
    state = _state(day=3)

    events = module.process_hero_unlocks(state, config, day=3)

    assert len(events) == 1
    assert events[0].hero_id == "hero_b"
    assert events[0].unique_cards_added == 2
