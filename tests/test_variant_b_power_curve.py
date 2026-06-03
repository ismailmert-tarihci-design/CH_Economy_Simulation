"""Tests for the Variant B bluestar -> power conversion (power_curve)."""

from __future__ import annotations

import pytest

from simulation.variants.variant_b.power_curve import (
    PowerTier,
    load_power_table,
    power_for_bluestars,
)


def test_table_loads_and_is_contiguous():
    table = load_power_table()
    assert table, "power table should be non-empty"
    for prev, cur in zip(table, table[1:]):
        assert cur.min_bluestar == prev.max_bluestar


def test_zero_and_negative_bluestars_give_unit_power():
    assert power_for_bluestars(0) == 1.0
    assert power_for_bluestars(-5) == 1.0


def test_reference_points_match_fitted_curve():
    # Anchors from the configured bluestar->power table. Tier 1 is tuned so the
    # first 30 bluestars exactly double power (1.023373892 ** 30 == 2.0); higher
    # anchors follow from the per-tier multipliers.
    assert power_for_bluestars(30) == pytest.approx(2.0, rel=0.01)
    assert power_for_bluestars(260) == pytest.approx(3.98, rel=0.02)
    assert power_for_bluestars(1000) == pytest.approx(13.84, rel=0.02)


def test_monotonic_increasing():
    prev = power_for_bluestars(0)
    for bs in range(100, 5000, 137):
        cur = power_for_bluestars(bs)
        assert cur >= prev
        prev = cur


def test_bluestar_gating_single_pass_does_not_cascade():
    """beat_chapters_by_bluestars must not cascade: with auto_upgrade=False it
    beats only the chapters the *current* bluestars already reach, never
    re-upgrading chapter-pack cards to fund further chapters within one call.
    """
    from random import Random

    from simulation.variants.variant_b.config_loader import load_defaults
    from simulation.variants.variant_b import day_simulator as ds
    from simulation.variants.variant_b.scripted_runner import beat_chapters_by_bluestars

    config = load_defaults()
    gs = ds.init_state(config)
    thresholds = [0, 100, 200, 300, 400, 500]  # chapters 1..6

    # No bluestars yet beyond start: a fresh state has 0 -> only chapters whose
    # threshold is 0 qualify, and never more than len(thresholds).
    gs.total_bluestars = 350
    gs.chapters_beaten = 0
    res = beat_chapters_by_bluestars(gs, config, thresholds, Random(1), auto_upgrade=False)
    # 350 reaches thresholds 0,100,200,300 -> 4 chapters, in a single pass.
    assert res["chapters"] == 4
    assert gs.chapters_beaten == 4
    assert res["hero_upgrades"] == 0 and res["shared_upgrades"] == 0
    # Re-running without more bluestars beats nothing further.
    res2 = beat_chapters_by_bluestars(gs, config, thresholds, Random(1), auto_upgrade=False)
    assert res2["chapters"] == 0


def test_custom_table_argument_is_used():
    table = [
        PowerTier(tier=1, min_bluestar=0, max_bluestar=10, multiplier=2.0),
        PowerTier(tier=2, min_bluestar=10, max_bluestar=100, multiplier=1.0),
    ]
    # 2 ** 3 = 8 for 3 bluestars in the first tier.
    assert power_for_bluestars(3, table) == pytest.approx(8.0)
    # First tier saturates (2**10), second tier multiplier is 1.0.
    assert power_for_bluestars(50, table) == pytest.approx(2.0 ** 10)
