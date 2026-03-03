import importlib
from random import Random

import pytest

from simulation.models import (
    CardCategory,
    CardTypesRange,
    CoinPerDuplicate,
    DuplicateRange,
    GameState,
    PackConfig,
    PetState,
    PetSystemConfig,
    PetTierConfig,
    PetTierRow,
    ProgressionMapping,
    SimConfig,
    StreakState,
    UpgradeTable,
)


def _pet_system_module():
    return importlib.import_module("simulation.pet_system")


def _build_config(tier_rows: list[PetTierRow]) -> SimConfig:
    tier_map = {row.tier: row for row in tier_rows}
    template = tier_rows[-1]
    full_tiers = [
        tier_map.get(
            tier,
            PetTierRow(
                tier=tier,
                summons_to_lvl_up=template.summons_to_lvl_up,
                rarity_probabilities=template.rarity_probabilities,
            ),
        )
        for tier in range(1, 16)
    ]

    upgrade = UpgradeTable(
        category=CardCategory.GOLD_SHARED,
        duplicate_costs=[1] * 100,
        coin_costs=[1] * 100,
        bluestar_rewards=[1] * 100,
    )
    duplicate_range = DuplicateRange(
        category=CardCategory.GOLD_SHARED,
        min_pct=[1.0] * 100,
        max_pct=[1.0] * 100,
    )
    coin_per_dupe = CoinPerDuplicate(
        category=CardCategory.GOLD_SHARED,
        coins_per_dupe=[1] * 100,
    )

    return SimConfig(
        packs=[
            PackConfig(
                name="dummy",
                card_types_table={0: CardTypesRange(min=1, max=1)},
            )
        ],
        upgrade_tables={
            CardCategory.GOLD_SHARED: upgrade,
            CardCategory.BLUE_SHARED: upgrade,
            CardCategory.UNIQUE: UpgradeTable(
                category=CardCategory.UNIQUE,
                duplicate_costs=[1] * 10,
                coin_costs=[1] * 10,
                bluestar_rewards=[1] * 10,
            ),
        },
        duplicate_ranges={
            CardCategory.GOLD_SHARED: duplicate_range,
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
            CardCategory.GOLD_SHARED: coin_per_dupe,
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
        pet_system_config=PetSystemConfig(tier_table=PetTierConfig(tiers=full_tiers)),
    )


def _build_game_state() -> GameState:
    return GameState(
        day=1,
        cards=[],
        coins=0,
        total_bluestars=0,
        streak_state=StreakState(
            streak_shared=0,
            streak_unique=0,
            streak_per_color={},
            streak_per_hero={},
        ),
        pet_state=PetState(),
    )


def test_process_pet_summons_deterministic_reproducible():
    tiers = [
        PetTierRow(tier=1, summons_to_lvl_up=2, rarity_probabilities={"Common": 100.0}),
        PetTierRow(tier=2, summons_to_lvl_up=99, rarity_probabilities={"Rare": 100.0}),
    ]
    config = _build_config(tiers)

    state_a = _build_game_state()
    state_b = _build_game_state()

    module = _pet_system_module()
    events_a = module.process_pet_summons(state_a, config, eggs_to_consume=3, rng=None)
    events_b = module.process_pet_summons(state_b, config, eggs_to_consume=3, rng=None)

    assert [e.rarity for e in events_a] == [e.rarity for e in events_b]
    assert [e.tier_after for e in events_a] == [e.tier_after for e in events_b]


def test_process_pet_summons_seeded_rng_reproducible():
    tiers = [
        PetTierRow(
            tier=1,
            summons_to_lvl_up=99,
            rarity_probabilities={"Common": 50.0, "Rare": 50.0},
        )
    ]
    config = _build_config(tiers)

    state_a = _build_game_state()
    state_b = _build_game_state()

    module = _pet_system_module()
    events_a = module.process_pet_summons(
        state_a, config, eggs_to_consume=5, rng=Random(42)
    )
    events_b = module.process_pet_summons(
        state_b, config, eggs_to_consume=5, rng=Random(42)
    )

    assert [e.rarity for e in events_a] == [e.rarity for e in events_b]


def test_process_pet_summons_first_duplicate_unlocks_ownership():
    tiers = [
        PetTierRow(tier=1, summons_to_lvl_up=99, rarity_probabilities={"Common": 100.0})
    ]
    config = _build_config(tiers)
    state = _build_game_state()

    events = _pet_system_module().process_pet_summons(
        state, config, eggs_to_consume=2, rng=None
    )

    assert events[0].owned_after is False
    assert events[1].owned_after is True
    assert state.pet_state is not None
    assert state.pet_state.owned_pets["common_pet"] is True


def test_process_pet_summons_requires_tier_table():
    config = _build_config(
        [
            PetTierRow(
                tier=1, summons_to_lvl_up=99, rarity_probabilities={"Common": 100.0}
            )
        ]
    )
    config.pet_system_config = PetSystemConfig(tier_table=None)

    with pytest.raises(ValueError, match="Missing pet_system_config.tier_table"):
        _pet_system_module().process_pet_summons(
            _build_game_state(), config, eggs_to_consume=1
        )
