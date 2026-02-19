"""
Tests for Monte Carlo simulation with Welford's online statistics.

Covers WelfordAccumulator accuracy, MCResult structure, reproducibility,
confidence intervals, memory safety, run limits, and performance.
"""

import time
import warnings
from unittest.mock import patch

import numpy as np
import pytest

from simulation.models import (
    CardCategory,
    CardTypesRange,
    CoinPerDuplicate,
    DuplicateRange,
    PackConfig,
    ProgressionMapping,
    SimConfig,
    UpgradeTable,
)
from simulation.monte_carlo import (
    DailyAccumulators,
    MCResult,
    WelfordAccumulator,
    run_monte_carlo,
)


@pytest.fixture
def full_config():
    """Create complete simulation configuration for Monte Carlo tests."""
    pack_config_1 = PackConfig(
        name="basic_pack",
        card_types_table={
            0: CardTypesRange(min=2, max=2),
            10: CardTypesRange(min=3, max=3),
            25: CardTypesRange(min=4, max=4),
        },
    )
    pack_config_2 = PackConfig(
        name="premium_pack",
        card_types_table={
            0: CardTypesRange(min=3, max=3),
            10: CardTypesRange(min=4, max=4),
            25: CardTypesRange(min=5, max=5),
        },
    )

    gold_upgrade_table = UpgradeTable(
        category=CardCategory.GOLD_SHARED,
        duplicate_costs=[50] * 100,
        coin_costs=[200] * 100,
        bluestar_rewards=[10] * 100,
    )
    blue_upgrade_table = UpgradeTable(
        category=CardCategory.BLUE_SHARED,
        duplicate_costs=[50] * 100,
        coin_costs=[200] * 100,
        bluestar_rewards=[10] * 100,
    )
    unique_upgrade_table = UpgradeTable(
        category=CardCategory.UNIQUE,
        duplicate_costs=[30] * 10,
        coin_costs=[150] * 10,
        bluestar_rewards=[5] * 10,
    )

    gold_dup_range = DuplicateRange(
        category=CardCategory.GOLD_SHARED,
        min_pct=[0.8] * 100,
        max_pct=[1.2] * 100,
    )
    blue_dup_range = DuplicateRange(
        category=CardCategory.BLUE_SHARED,
        min_pct=[0.8] * 100,
        max_pct=[1.2] * 100,
    )
    unique_dup_range = DuplicateRange(
        category=CardCategory.UNIQUE,
        min_pct=[0.8] * 10,
        max_pct=[1.2] * 10,
    )

    gold_coin_per_dup = CoinPerDuplicate(
        category=CardCategory.GOLD_SHARED,
        coins_per_dupe=[2] * 100,
    )
    blue_coin_per_dup = CoinPerDuplicate(
        category=CardCategory.BLUE_SHARED,
        coins_per_dupe=[2] * 100,
    )
    unique_coin_per_dup = CoinPerDuplicate(
        category=CardCategory.UNIQUE,
        coins_per_dupe=[5] * 10,
    )

    progression_mapping = ProgressionMapping(
        shared_levels=[1, 5, 10, 20, 40, 60, 80],
        unique_levels=[1, 2, 3, 4, 6, 8, 10],
    )

    return SimConfig(
        packs=[pack_config_1, pack_config_2],
        upgrade_tables={
            CardCategory.GOLD_SHARED: gold_upgrade_table,
            CardCategory.BLUE_SHARED: blue_upgrade_table,
            CardCategory.UNIQUE: unique_upgrade_table,
        },
        duplicate_ranges={
            CardCategory.GOLD_SHARED: gold_dup_range,
            CardCategory.BLUE_SHARED: blue_dup_range,
            CardCategory.UNIQUE: unique_dup_range,
        },
        coin_per_duplicate={
            CardCategory.GOLD_SHARED: gold_coin_per_dup,
            CardCategory.BLUE_SHARED: blue_coin_per_dup,
            CardCategory.UNIQUE: unique_coin_per_dup,
        },
        progression_mapping=progression_mapping,
        unique_unlock_schedule={1: 8, 30: 1, 60: 1},
        daily_pack_schedule=[{"basic_pack": 3.5, "premium_pack": 2.0}],
        num_days=100,
    )


def test_welford_accuracy():
    """Test WelfordAccumulator matches numpy mean/std."""
    accumulator = WelfordAccumulator()
    data = [2, 4, 4, 4, 5, 5, 7, 9]

    for value in data:
        accumulator.update(value)

    mean, std = accumulator.result()

    np_mean = np.mean(data)
    np_std = np.std(data, ddof=1)

    assert abs(mean - np_mean) < 0.01, f"Mean mismatch: {mean} vs {np_mean}"
    assert abs(std - np_std) < 0.01, f"Std mismatch: {std} vs {np_std}"


def test_mc_10runs(full_config):
    """Test 10-run MC produces valid MCResult."""
    result = run_monte_carlo(full_config, num_runs=10)

    assert result.num_runs == 10
    assert result.bluestar_stats.count == 10
    assert len(result.daily_bluestar_means) == 100
    assert len(result.daily_bluestar_stds) == 100
    assert len(result.daily_coin_balance_means) == 100
    assert len(result.daily_coin_balance_stds) == 100
    assert result.completion_time > 0

    assert "GOLD_SHARED" in result.daily_category_level_means
    assert "BLUE_SHARED" in result.daily_category_level_means
    assert "UNIQUE" in result.daily_category_level_means

    mean, std = result.bluestar_stats.result()
    assert mean > 0
    assert std >= 0


def test_reproducibility(full_config):
    """Test reproducibility — same config → same results."""
    result1 = run_monte_carlo(full_config, num_runs=10)
    result2 = run_monte_carlo(full_config, num_runs=10)

    mean1, _ = result1.bluestar_stats.result()
    mean2, _ = result2.bluestar_stats.result()

    assert abs(mean1 - mean2) < 0.001, f"Reproducibility failed: {mean1} vs {mean2}"

    for i in range(100):
        assert (
            abs(result1.daily_bluestar_means[i] - result2.daily_bluestar_means[i])
            < 0.001
        )


def test_confidence_intervals():
    """Test confidence intervals narrow with more runs."""
    accumulator_10 = WelfordAccumulator()
    accumulator_100 = WelfordAccumulator()

    np.random.seed(42)
    data = np.random.normal(100, 15, 1000)

    for value in data[:10]:
        accumulator_10.update(float(value))

    for value in data[:100]:
        accumulator_100.update(float(value))

    ci_10_lower, ci_10_upper = accumulator_10.confidence_interval()
    ci_100_lower, ci_100_upper = accumulator_100.confidence_interval()

    width_10 = ci_10_upper - ci_10_lower
    width_100 = ci_100_upper - ci_100_lower

    assert width_100 < width_10, (
        f"CI width should decrease with more samples: {width_100} >= {width_10}"
    )


def test_memory_safety(full_config):
    """Test 100-run MC doesn't store 100 SimResults."""
    config = full_config
    config.num_days = 10

    with patch("simulation.monte_carlo.run_simulation") as mock_run_sim:
        from simulation.orchestrator import run_simulation

        actual_run = run_simulation

        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            return actual_run(*args, **kwargs)

        mock_run_sim.side_effect = side_effect

        result = run_monte_carlo(config, num_runs=20)

        assert call_count[0] == 20, f"Expected 20 simulation calls, got {call_count[0]}"
        assert result.num_runs == 20


def test_hard_cap_500():
    """Test hard cap at 500 runs enforced."""
    config = SimConfig(
        packs=[],
        upgrade_tables={},
        duplicate_ranges={},
        coin_per_duplicate={},
        progression_mapping=ProgressionMapping(shared_levels=[1], unique_levels=[1]),
        unique_unlock_schedule={},
        daily_pack_schedule=[],
        num_days=1,
    )

    with pytest.raises(ValueError, match="num_runs must be between 1 and 500"):
        run_monte_carlo(config, num_runs=501)

    with pytest.raises(ValueError, match="num_runs must be between 1 and 500"):
        run_monte_carlo(config, num_runs=0)


def test_performance_100_100(full_config):
    """Test 100-run × 100-day MC completes in < 120 seconds."""
    start = time.time()
    result = run_monte_carlo(full_config, num_runs=100)
    elapsed = time.time() - start

    assert result.num_runs == 100
    assert len(result.daily_bluestar_means) == 100
    assert elapsed < 120.0, f"Performance test failed: {elapsed:.2f}s > 120s"
    assert result.completion_time < 120.0


def test_warning_200_runs(full_config):
    """Test warning issued when num_runs > 200."""
    config = full_config
    config.num_days = 10

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        run_monte_carlo(config, num_runs=201)

        assert len(w) == 1
        assert issubclass(w[0].category, UserWarning)
        assert "num_runs=201 is large" in str(w[0].message)


def test_daily_accumulators():
    """Test DailyAccumulators update and finalize correctly."""
    from simulation.orchestrator import DailySnapshot

    accumulators = DailyAccumulators(num_days=3)

    snapshot1 = DailySnapshot(
        day=1,
        total_bluestars=100,
        bluestars_earned_today=10,
        coins_balance=500,
        coins_earned_today=50,
        coins_spent_today=20,
        card_levels={},
        upgrades_today=[],
        category_avg_levels={"GOLD_SHARED": 5.0, "BLUE_SHARED": 3.0, "UNIQUE": 2.0},
        total_unique_unlocked=8,
        pull_counts_by_type={},
        pack_counts_by_type={},
    )

    snapshot2 = DailySnapshot(
        day=1,
        total_bluestars=105,
        bluestars_earned_today=15,
        coins_balance=520,
        coins_earned_today=60,
        coins_spent_today=25,
        card_levels={},
        upgrades_today=[],
        category_avg_levels={"GOLD_SHARED": 5.5, "BLUE_SHARED": 3.2, "UNIQUE": 2.1},
        total_unique_unlocked=8,
        pull_counts_by_type={},
        pack_counts_by_type={},
    )

    accumulators.update_from_snapshot(0, snapshot1)
    accumulators.update_from_snapshot(0, snapshot2)

    stats = accumulators.finalize()

    assert abs(stats["bluestar_means"][0] - 102.5) < 0.1
    assert abs(stats["coin_balance_means"][0] - 510.0) < 0.1

    assert abs(stats["category_level_means"]["GOLD_SHARED"][0] - 5.25) < 0.1
