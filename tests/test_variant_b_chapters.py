"""Tests for cohort-driven chapter beats in the Variant B big simulator.

The day-by-day simulator opens an `EndOfChapterPack` for every chapter beaten,
driven by `chapters_per_day` from the active cohort profile (Average/P75/P90).
These tests confirm the big orchestrator now does the same thing, and that
Monte Carlo's per-day pack-count aggregation rides the new packs through.
"""

from __future__ import annotations

from random import Random

import pytest

from simulation.monte_carlo import run_monte_carlo
from simulation.variants.variant_b.config_loader import load_defaults
from simulation.variants.variant_b.chapter_schedule import (
    chapters_for_sim_day,
    load_cohort_chapters,
)
from simulation.variants.variant_b.ftue import FTUE_END_CHAPTER
from simulation.variants.variant_b.orchestrator import run_simulation


# Keep the run small but long enough to cycle the schedule once. The default
# config is for 730 days which is overkill for unit testing.
SHORT_RUN_DAYS = 10


@pytest.fixture
def short_config():
    """Short Variant B config with the daily-schedule's `EndOfChapterPack`
    entries zeroed out so that any EndOfChapterPack packs seen in the result
    are unambiguously driven by `chapters_per_day`."""
    config = load_defaults()
    config.num_days = SHORT_RUN_DAYS
    for day_entry in config.daily_pack_schedule:
        if "EndOfChapterPack" in day_entry:
            day_entry["EndOfChapterPack"] = 0.0
    return config


def test_chapters_for_sim_day_lookup():
    schedule = [0, 1, 2, 3]
    assert chapters_for_sim_day(schedule, 0) == 0   # install day
    assert chapters_for_sim_day(schedule, 1) == 0   # day 1 -> idx 0
    assert chapters_for_sim_day(schedule, 4) == 3
    assert chapters_for_sim_day(schedule, 5) == 0   # wraps
    assert chapters_for_sim_day([], 3) == 0


def test_run_simulation_beats_chapters(short_config):
    """Big sim should open one EndOfChapterPack per chapter in schedule."""
    # Use a small fixed schedule so the expected totals are obvious.
    short_config.chapters_per_day = [0, 1, 2, 1, 0, 3, 0, 1, 2, 1]
    scheduled_total = sum(short_config.chapters_per_day[:SHORT_RUN_DAYS])

    result = run_simulation(short_config, rng=Random(7))

    # game_state.chapters_beaten total = FTUE baseline + schedule sum.
    last_snapshot = result.daily_snapshots[-1]
    assert last_snapshot.chapters_beaten_total == FTUE_END_CHAPTER + scheduled_total

    # Per-day snapshot fields should mirror the schedule entries (FTUE bump
    # happens before day 1 and is not attributed to any in-loop day).
    for idx, snap in enumerate(result.daily_snapshots):
        assert snap.chapters_beaten_today == short_config.chapters_per_day[idx], (
            f"day {idx + 1}: expected {short_config.chapters_per_day[idx]} chapters, "
            f"got {snap.chapters_beaten_today}"
        )

    # EndOfChapterPack pulls (only from in-loop chapter beats — FTUE bumps
    # the counter without opening packs).
    total_eoc_packs = sum(
        snap.pack_counts_by_type.get("EndOfChapterPack", 0)
        for snap in result.daily_snapshots
    )
    assert total_eoc_packs == scheduled_total


def test_run_simulation_no_chapters_when_schedule_empty(short_config):
    short_config.chapters_per_day = []
    result = run_simulation(short_config, rng=Random(1))

    last = result.daily_snapshots[-1]
    assert last.chapters_beaten_total == FTUE_END_CHAPTER
    for snap in result.daily_snapshots:
        assert snap.chapters_beaten_today == 0
        assert snap.pack_counts_by_type.get("EndOfChapterPack", 0) == 0


def test_average_cohort_profile_provides_chapters_per_day():
    """The cohort helper should read the canonical Average profile."""
    schedule = load_cohort_chapters("Average")
    assert schedule, "Average profile should ship a non-empty chapters_per_day"
    # Day 0 should be 0 (install/FTUE day).
    assert schedule[0] == 0


def test_monte_carlo_aggregates_endofchapter_packs(short_config):
    """MC's per-day pack_count_means should pick up EndOfChapterPack."""
    short_config.chapters_per_day = [0, 2, 2, 2, 2, 2, 2, 2, 2, 2]
    expected_total = sum(short_config.chapters_per_day[:SHORT_RUN_DAYS])

    mc = run_monte_carlo(short_config, num_runs=3, run_fn=run_simulation)

    eoc_means = mc.daily_pack_count_means.get("EndOfChapterPack")
    assert eoc_means is not None, "MC should aggregate EndOfChapterPack counts"
    # Each individual seed should beat exactly the schedule; mean must equal it.
    assert sum(eoc_means) == pytest.approx(float(expected_total))
    for day_idx, scheduled in enumerate(short_config.chapters_per_day[:SHORT_RUN_DAYS]):
        assert eoc_means[day_idx] == pytest.approx(float(scheduled))
