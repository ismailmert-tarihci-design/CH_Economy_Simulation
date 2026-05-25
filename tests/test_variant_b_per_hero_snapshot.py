"""Tests for per-hero daily snapshot data in the Variant B big simulator.

Task 3 of 4 introduced `HeroCardDailySnapshot.hero_states` — a
`Dict[hero_id, HeroDailySnapshot]` populated every day for every unlocked
hero. These tests confirm the orchestrator wires that field correctly and
that Monte Carlo's per-hero accumulators surface the data.
"""

from __future__ import annotations

from random import Random

import pytest

from simulation.monte_carlo import run_monte_carlo
from simulation.variants.variant_b.config_loader import load_defaults
from simulation.variants.variant_b.models import HeroDailySnapshot
from simulation.variants.variant_b.orchestrator import run_simulation


SHORT_RUN_DAYS = 6


@pytest.fixture
def short_config():
    config = load_defaults()
    config.num_days = SHORT_RUN_DAYS
    return config


def test_daily_snapshot_carries_hero_states(short_config):
    """Every snapshot should have a hero_states dict, one entry per unlocked hero."""
    result = run_simulation(short_config, rng=Random(1))

    assert result.daily_snapshots, "expected at least one daily snapshot"

    for day_idx, snap in enumerate(result.daily_snapshots):
        # The unlock schedule may add heroes mid-run; at the very least the
        # final snapshot must include every hero the run finished with.
        assert hasattr(snap, "hero_states"), f"day {day_idx + 1}: missing hero_states"
        assert isinstance(snap.hero_states, dict)
        for hid, hero_snap in snap.hero_states.items():
            assert isinstance(hero_snap, HeroDailySnapshot)
            assert hero_snap.level >= 1
            assert hero_snap.xp >= 0
            assert hero_snap.joker_count >= 0
            assert hero_snap.total_cards >= 0
            # cards_by_rarity totals should match total_cards.
            assert sum(hero_snap.cards_by_rarity.values()) == hero_snap.total_cards

    # The final snapshot's hero_states should include every hero the result
    # reports a final level for.
    final = result.daily_snapshots[-1]
    assert set(final.hero_states.keys()) == set(result.final_hero_levels.keys())
    for hid, level in result.final_hero_levels.items():
        assert final.hero_states[hid].level == level


def test_hero_states_track_levels_non_decreasing(short_config):
    """Hero level must be non-decreasing across the run (no de-leveling)."""
    result = run_simulation(short_config, rng=Random(2))

    first = result.daily_snapshots[0]
    assert first.hero_states, "expected hero_states populated on day 1"

    # Validate non-decreasing levels for every hero that lives through the run.
    for hid in first.hero_states:
        levels = []
        for snap in result.daily_snapshots:
            hs = snap.hero_states.get(hid)
            if hs is not None:
                levels.append(hs.level)
        assert all(b >= a for a, b in zip(levels, levels[1:])), (
            f"{hid} level should be monotonically non-decreasing, got {levels}"
        )

    # Sanity: at least one hero should hit a non-empty cards_by_rarity entry.
    last = result.daily_snapshots[-1]
    assert any(
        sum(hs.cards_by_rarity.values()) > 0 for hs in last.hero_states.values()
    )


def test_monte_carlo_aggregates_per_hero(short_config):
    """MC should expose per-hero per-day level/xp/joker/total_cards means+stds."""
    mc = run_monte_carlo(short_config, num_runs=2, run_fn=run_simulation)

    assert mc.daily_hero_level_means, "expected MC to aggregate per-hero levels"
    assert mc.daily_hero_xp_means
    assert mc.daily_hero_joker_means
    assert mc.daily_hero_total_cards_means

    # Every per-hero series should be exactly num_days long.
    for hid, series in mc.daily_hero_level_means.items():
        assert len(series) == SHORT_RUN_DAYS
        assert all(v >= 0.0 for v in series)
    # Stds must match the means in shape, hero-by-hero.
    for hid in mc.daily_hero_level_means:
        assert hid in mc.daily_hero_level_stds
        assert len(mc.daily_hero_level_stds[hid]) == SHORT_RUN_DAYS
