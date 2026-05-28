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
    chapters_for_bluestars,
    chapters_for_sim_day,
    load_cohort_chapters,
    load_default_bluestar_thresholds,
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
    are unambiguously driven by chapter beating.

    Also clears `chapter_bluestar_thresholds` so the legacy calendar
    `chapters_per_day` schedule is what's being exercised. Threshold-mode
    behaviour has its own dedicated test below.
    """
    config = load_defaults()
    config.num_days = SHORT_RUN_DAYS
    config.chapter_bluestar_thresholds = []
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


def test_chapters_for_bluestars_lookup():
    thresholds = [0, 10, 50, 200, 500]
    # No bluestars yet → chapter 1 only (threshold 0).
    assert chapters_for_bluestars(thresholds, 0, 0) == 1
    # Crossed threshold for chapters 1-3, none beaten yet.
    assert chapters_for_bluestars(thresholds, 75, 0) == 3
    # Already beaten the 3 we can; nothing to add.
    assert chapters_for_bluestars(thresholds, 75, 3) == 0
    # Past the table we linearly extrapolate the curve using the last
    # two entries' step (here step = 500 - 200 = 300). One extra chapter
    # for each `step` bluestars beyond `thresholds[-1]`.
    # bs=800 → table-target=5 (covers all 5 entries), extra = (800-500)//300 = 1.
    assert chapters_for_bluestars(thresholds, 800, 0) == 6
    # bs=100_000 → 5 + (100000-500)//300 = 5 + 331 = 336.
    assert chapters_for_bluestars(thresholds, 100_000, 0) == 336
    # Single-entry table cannot extrapolate (no step) — caps at 1.
    assert chapters_for_bluestars([0.0], 100_000, 0) == 1
    # Flat-tail table (step <= 0) cannot extrapolate — caps at len.
    assert chapters_for_bluestars([0, 10, 50, 50], 100_000, 0) == 4
    # Empty table = no chapters.
    assert chapters_for_bluestars([], 999, 0) == 0


def test_default_bluestar_thresholds_load():
    table = load_default_bluestar_thresholds()
    assert table, "Default `All` cohort thresholds should be non-empty"
    # Chapter 1 is unlocked from the start (0 bs required).
    assert table[0] == 0
    # Monotonic non-decreasing — beating chapter N+1 always costs ≥ chapter N.
    for i in range(1, len(table)):
        assert table[i] >= table[i - 1], f"thresholds[{i}] decreased"


def test_big_sim_uses_bluestar_thresholds_when_set():
    """When `chapter_bluestar_thresholds` is configured the big sim should
    beat chapters as bluestars cross thresholds — *not* on the calendar."""
    config = load_defaults()
    config.num_days = 5
    # FTUE auto-beats the first FTUE_END_CHAPTER chapters before day 1, so
    # those slots in the threshold list are 0 (always satisfied). Chapter 7
    # gets a tiny 10-bs gate (expected to fire), chapter 8 gets an
    # unreachable gate (must not fire).
    config.chapter_bluestar_thresholds = (
        [0.0] * FTUE_END_CHAPTER + [10.0, 1e7]
    )
    # Zero out the calendar schedule so a calendar fallback would yield 0
    # chapters — proving the threshold path is what's firing.
    config.chapters_per_day = []
    for day_entry in config.daily_pack_schedule:
        if "EndOfChapterPack" in day_entry:
            day_entry["EndOfChapterPack"] = 0.0

    result = run_simulation(config, rng=Random(11))

    last = result.daily_snapshots[-1]
    # Chapter 1 (threshold 0) and chapter 2 (threshold 10) get beaten once
    # the player accumulates at least 10 bluestars. Chapter 3 (1e7) does not.
    # FTUE_END_CHAPTER bumps chapters_beaten without opening EoC packs, so
    # the EoC pack count is what we assert against (the actual beats).
    total_eoc = sum(
        s.pack_counts_by_type.get("EndOfChapterPack", 0)
        for s in result.daily_snapshots
    )
    assert total_eoc == 1, (
        f"Expected exactly 1 EoC pack (chapter 7), got {total_eoc}. "
        f"chapters_beaten_total={last.chapters_beaten_total}"
    )
    assert last.chapters_beaten_total == FTUE_END_CHAPTER + 1


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
