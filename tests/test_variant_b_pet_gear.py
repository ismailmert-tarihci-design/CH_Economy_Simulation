"""Tests for per-hero pet & gear progression in Variant B (Task 4).

Covers:
  * Big simulator: schedules PetPacks and GearPacks via daily_pack_schedule
    and asserts the target hero's pet + gear state advance, and that the
    daily snapshot reflects the new state.
  * Day-by-day simulator: opens a PetPack and a GearPack via
    `open_pack_by_name()` and asserts the most-recently-unlocked hero's
    pet and gear state changed.
"""

from __future__ import annotations

from random import Random

import pytest

from simulation.monte_carlo import run_monte_carlo
from simulation.variants.variant_b import day_simulator as ds
from simulation.variants.variant_b.config_loader import load_defaults
from simulation.variants.variant_b.models import HeroDailySnapshot
from simulation.variants.variant_b.orchestrator import run_simulation
from simulation.variants.variant_b.pet_gear import (
    GEAR_MAX_LEVEL,
    HERO_GEAR_SLOTS,
    apply_gear_pack,
    apply_pet_pack,
    pick_pack_target,
)


# Short run keeps tests fast — long enough for several pack opens.
SHORT_RUN_DAYS = 5


def _build_short_config():
    """Variant B config with PetPack + GearPack heavy daily schedule."""
    config = load_defaults()
    config.num_days = SHORT_RUN_DAYS
    # Hot-wire the daily schedule to open lots of PetPack + GearPack per day
    # so the test's small run reliably exercises the new code path.
    config.daily_pack_schedule = [{"PetPack": 5.0, "GearPack": 5.0}] * SHORT_RUN_DAYS
    # Zero out chapter scheduling so EndOfChapterPack noise doesn't muddy the
    # pet/gear assertion target.
    config.chapters_per_day = []
    return config


def test_big_sim_advances_pet_and_gear_state():
    """Big sim with scheduled PetPacks/GearPacks should advance hero state."""
    config = _build_short_config()
    result = run_simulation(config, rng=Random(42))

    # Final snapshot must reveal pet/gear progression on at least one hero.
    assert result.daily_snapshots, "expected at least one daily snapshot"
    final = result.daily_snapshots[-1]
    assert final.hero_states, "expected hero_states on final snapshot"

    # At least one hero must have advanced its pet level past 1.
    max_pet_level = max(hs.pet_level for hs in final.hero_states.values())
    assert max_pet_level > 1, (
        f"Expected at least one hero to gain a pet level after "
        f"{SHORT_RUN_DAYS} days of scheduled PetPacks; got max pet_level "
        f"{max_pet_level}"
    )

    # At least one hero must have a gear slot above level 1.
    max_gear_total = max(hs.gear_total_level for hs in final.hero_states.values())
    expected_min_gear = len(HERO_GEAR_SLOTS)  # every slot starts at L1
    assert max_gear_total > expected_min_gear, (
        f"Expected gear_total_level to exceed baseline {expected_min_gear} for "
        f"at least one hero; got max {max_gear_total}"
    )

    # Snapshots are HeroDailySnapshot dataclasses with the new fields.
    sample = next(iter(final.hero_states.values()))
    assert isinstance(sample, HeroDailySnapshot)
    assert hasattr(sample, "pet_level")
    assert hasattr(sample, "gear_levels")
    assert hasattr(sample, "gear_total_level")
    # gear_levels must sum to gear_total_level for every hero.
    for hs in final.hero_states.values():
        assert sum(hs.gear_levels.values()) == hs.gear_total_level


def test_big_sim_pet_gear_monotonic_non_decreasing():
    """Pet level and gear total level must never go backwards across the run."""
    config = _build_short_config()
    result = run_simulation(config, rng=Random(7))

    first = result.daily_snapshots[0]
    assert first.hero_states

    for hid in first.hero_states:
        pets = []
        gears = []
        for snap in result.daily_snapshots:
            hs = snap.hero_states.get(hid)
            if hs is None:
                continue
            pets.append(hs.pet_level)
            gears.append(hs.gear_total_level)
        assert all(b >= a for a, b in zip(pets, pets[1:])), (
            f"{hid} pet_level should be non-decreasing, got {pets}"
        )
        assert all(b >= a for a, b in zip(gears, gears[1:])), (
            f"{hid} gear_total_level should be non-decreasing, got {gears}"
        )


def test_monte_carlo_aggregates_pet_and_gear():
    """MC should expose per-hero per-day pet-level / gear-total means+stds."""
    config = _build_short_config()
    mc = run_monte_carlo(config, num_runs=2, run_fn=run_simulation)

    assert mc.daily_hero_pet_level_means, "expected MC to aggregate pet levels"
    assert mc.daily_hero_gear_total_level_means, "expected MC to aggregate gear total levels"

    for hid, series in mc.daily_hero_pet_level_means.items():
        assert len(series) == SHORT_RUN_DAYS
        assert all(v >= 0.0 for v in series)
        assert hid in mc.daily_hero_pet_level_stds
        assert len(mc.daily_hero_pet_level_stds[hid]) == SHORT_RUN_DAYS

    for hid, series in mc.daily_hero_gear_total_level_means.items():
        assert len(series) == SHORT_RUN_DAYS
        assert all(v >= 0.0 for v in series)


def test_day_simulator_open_pet_pack_advances_target_hero():
    """Day-by-day sim: PetPack opened via open_pack_by_name advances pet state."""
    config = load_defaults()
    state = ds.init_state(config)

    # Day-0 starter (Woody) should be set as last_unlocked_hero by init_state.
    target = pick_pack_target(state)
    assert target is not None
    assert target == state.last_unlocked_hero

    before = state.heroes[target].pet.level
    before_packs = state.heroes[target].pet.pet_packs_opened
    before_xp = state.heroes[target].pet.xp

    result = ds.open_pack_by_name("PetPack", state, config, Random(123))

    after = state.heroes[target].pet
    assert after.pet_packs_opened == before_packs + 1
    # XP must have advanced (either bumped level or stayed under threshold).
    if after.level == before:
        assert after.xp > before_xp
    else:
        assert after.level > before

    # The pack-open result should carry the pet_event so UI can read it.
    assert result["pet_event"] is not None
    assert result["pet_event"].hero_id == target


def test_day_simulator_open_gear_pack_advances_target_hero():
    """Day-by-day sim: GearPack opened via open_pack_by_name bumps a gear slot."""
    config = load_defaults()
    state = ds.init_state(config)

    target = pick_pack_target(state)
    assert target is not None
    hero_state = state.heroes[target]
    before_total = sum(hero_state.gear.slot_levels.values())
    before_packs = hero_state.gear.gear_packs_opened

    result = ds.open_pack_by_name("GearPack", state, config, Random(99))

    assert hero_state.gear.gear_packs_opened == before_packs + 1
    after_total = sum(hero_state.gear.slot_levels.values())
    assert after_total == before_total + 1, (
        f"Expected exactly one slot to bump by one level; "
        f"before={before_total} after={after_total}"
    )
    assert result["gear_event"] is not None
    assert result["gear_event"].hero_id == target
    assert result["gear_event"].new_level == result["gear_event"].old_level + 1


def test_apply_pet_pack_unit_caps_at_max_level():
    """Pet level should not exceed PET_MAX_LEVEL even with many opens."""
    from simulation.variants.variant_b.pet_gear import PET_MAX_LEVEL
    from simulation.variants.variant_b.models import HeroProgressState

    hero = HeroProgressState(hero_id="hero_test")
    for _ in range(PET_MAX_LEVEL * 5):
        apply_pet_pack(hero)
    assert hero.pet.level == PET_MAX_LEVEL


def test_apply_gear_pack_round_robin_distributes():
    """Sequential GearPacks should spread across HERO_GEAR_SLOTS round-robin."""
    from simulation.variants.variant_b.models import HeroProgressState

    hero = HeroProgressState(hero_id="hero_rr")
    # Open exactly one pack per slot — total = num_slots, each slot +1.
    for _ in range(len(HERO_GEAR_SLOTS)):
        apply_gear_pack(hero)
    for slot in HERO_GEAR_SLOTS:
        assert hero.gear.slot_levels[slot] == 2, (
            f"slot {slot} expected L2 after round-robin, got "
            f"{hero.gear.slot_levels[slot]}"
        )


def test_pick_pack_target_prefers_last_unlocked():
    """pick_pack_target should follow last_unlocked_hero when set."""
    from simulation.variants.variant_b.models import (
        HeroCardGameState,
        HeroProgressState,
    )

    state = HeroCardGameState()
    state.heroes["first"] = HeroProgressState(hero_id="first")
    state.heroes["second"] = HeroProgressState(hero_id="second")
    state.last_unlocked_hero = "second"
    assert pick_pack_target(state) == "second"

    # Fallback when last_unlocked_hero is unset/stale — pick most-recent dict entry.
    state.last_unlocked_hero = None
    assert pick_pack_target(state) == "second"

    state.last_unlocked_hero = "ghost_hero"  # stale
    assert pick_pack_target(state) == "second"


def test_pick_pack_target_returns_none_when_no_heroes():
    from simulation.variants.variant_b.models import HeroCardGameState

    state = HeroCardGameState()
    assert pick_pack_target(state) is None
