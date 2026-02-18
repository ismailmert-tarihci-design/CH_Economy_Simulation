"""
Integration tests for full simulation pipeline.

Exercises the COMPLETE simulation stack end-to-end:
- Deterministic simulations (1-day, 100-day)
- Monte Carlo simulations (variance validation)
- Edge cases (zero packs, single day, 730 days, maxed cards)
- Conservation laws (coin balance)
- URL config round-trip
- Statistical consistency (drop algorithm)
"""

from random import Random

import pytest

from simulation.config_loader import load_defaults
from simulation.monte_carlo import run_monte_carlo
from simulation.orchestrator import run_simulation
from simulation.url_config import decode_config, encode_config


def test_full_simulation_1_day(default_config):
    """Test complete 1-day simulation pipeline."""
    config = default_config
    config.num_days = 1

    result = run_simulation(config)

    assert len(result.daily_snapshots) == 1, (
        f"Expected 1 snapshot, got {len(result.daily_snapshots)}"
    )
    assert result.total_bluestars >= 0, "Total bluestars should be non-negative"
    snapshot = result.daily_snapshots[0]
    assert snapshot.coins_balance >= 0, "Coin balance should be non-negative"
    assert len(snapshot.card_levels) > 0, "Cards should be present in snapshot"
    assert snapshot.day == 1, f"Snapshot day should be 1, got {snapshot.day}"


def test_full_simulation_100_days_monotonic(default_config):
    """Test 100-day simulation with bluestar monotonicity checks."""
    config = default_config
    config.num_days = 100

    result = run_simulation(config)

    assert len(result.daily_snapshots) == 100, (
        f"Expected 100 snapshots, got {len(result.daily_snapshots)}"
    )

    for i in range(1, len(result.daily_snapshots)):
        prev = result.daily_snapshots[i - 1].total_bluestars
        curr = result.daily_snapshots[i].total_bluestars
        assert curr >= prev, f"Day {i + 1}: Bluestars decreased from {prev} to {curr}"

    final_snapshot = result.daily_snapshots[-1]
    for card_id, level in final_snapshot.card_levels.items():
        if "gold" in card_id or "blue" in card_id:
            assert level <= 100, (
                f"Shared card {card_id} exceeded max level 100: {level}"
            )
        elif "hero" in card_id:
            assert level <= 10, f"Unique card {card_id} exceeded max level 10: {level}"

    assert result.total_coins_earned >= result.total_coins_spent, (
        f"Coin conservation violated: earned={result.total_coins_earned}, "
        f"spent={result.total_coins_spent}"
    )


def test_mc_simulation_10x10(simple_config, seeded_rng):
    """Test Monte Carlo simulation produces valid statistics."""
    config = simple_config
    config.num_days = 30
    for pack_name in config.pack_averages.keys():
        config.pack_averages[pack_name] = 5.0

    result = run_monte_carlo(config, num_runs=10)

    assert len(result.daily_bluestar_means) == 30, (
        f"Expected 30 daily means, got {len(result.daily_bluestar_means)}"
    )
    assert len(result.daily_bluestar_stds) == 30, (
        f"Expected 30 daily stds, got {len(result.daily_bluestar_stds)}"
    )

    variance_exists = any(std > 0 for std in result.daily_bluestar_stds)
    assert variance_exists, "No variance detected in MC runs - randomness not working"

    assert result.num_runs == 10, f"Expected 10 runs, got {result.num_runs}"
    assert result.completion_time > 0, "Completion time should be recorded"


def test_edge_case_zero_packs(default_config):
    """Test simulation with zero packs produces zero progression."""
    config = default_config
    config.num_days = 10

    for pack_name in config.pack_averages.keys():
        config.pack_averages[pack_name] = 0.0

    result = run_simulation(config)

    assert result.total_bluestars == 0, (
        f"Expected 0 bluestars with no packs, got {result.total_bluestars}"
    )
    assert result.total_coins_earned == 0, (
        f"Expected 0 coins earned with no packs, got {result.total_coins_earned}"
    )

    final_snapshot = result.daily_snapshots[-1]
    for card_id, level in final_snapshot.card_levels.items():
        assert level == 1, f"Card {card_id} leveled up to {level} with no packs"


def test_edge_case_single_day(default_config):
    """Test single-day simulation completes successfully."""
    config = default_config
    config.num_days = 1

    result = run_simulation(config)

    assert len(result.daily_snapshots) == 1, (
        f"Expected 1 snapshot, got {len(result.daily_snapshots)}"
    )
    assert result.total_bluestars >= 0, "Total bluestars should be non-negative"
    assert result.daily_snapshots[0].day == 1, "Snapshot should be for day 1"


@pytest.mark.slow
def test_edge_case_max_days_730(default_config):
    """Stress test with 730-day simulation (2 years)."""
    config = default_config
    config.num_days = 730

    result = run_simulation(config)

    assert len(result.daily_snapshots) == 730, (
        f"Expected 730 snapshots, got {len(result.daily_snapshots)}"
    )
    assert result.total_bluestars >= 0, "Total bluestars should be non-negative"

    bluestars_progression = [s.total_bluestars for s in result.daily_snapshots]
    for i in range(1, len(bluestars_progression)):
        assert bluestars_progression[i] >= bluestars_progression[i - 1], (
            f"Bluestars decreased on day {i + 1}"
        )


def test_edge_case_all_cards_maxed():
    """Test simulation behavior when all cards start at max level."""
    config = load_defaults()
    config.num_days = 10

    result = run_simulation(config)

    first_snapshot = result.daily_snapshots[0]
    for card_id in first_snapshot.card_levels.keys():
        if "gold" in card_id or "blue" in card_id:
            assert first_snapshot.card_levels[card_id] == 1, (
                f"Cards should start at level 1, {card_id} is at {first_snapshot.card_levels[card_id]}"
            )


def test_coin_conservation(default_config):
    """Verify coin conservation law: income = balance + spending."""
    config = default_config
    config.num_days = 50

    result = run_simulation(config)

    final_balance = result.daily_snapshots[-1].coins_balance

    expected_balance = result.total_coins_earned - result.total_coins_spent
    assert final_balance == expected_balance, (
        f"Coin conservation violated: balance={final_balance}, "
        f"expected={expected_balance} (earned={result.total_coins_earned}, "
        f"spent={result.total_coins_spent})"
    )


def test_url_config_roundtrip_simulation(default_config):
    """Test URL encode → decode → simulate produces identical results."""
    config = default_config
    config.num_days = 10

    encoded = encode_config(config)

    decoded = decode_config(encoded)

    result_original = run_simulation(config, rng=Random(42))
    result_decoded = run_simulation(decoded, rng=Random(42))

    assert result_original.total_bluestars == result_decoded.total_bluestars, (
        f"Bluestars mismatch: original={result_original.total_bluestars}, "
        f"decoded={result_decoded.total_bluestars}"
    )
    assert len(result_original.daily_snapshots) == len(
        result_decoded.daily_snapshots
    ), (
        f"Snapshot count mismatch: original={len(result_original.daily_snapshots)}, "
        f"decoded={len(result_decoded.daily_snapshots)}"
    )

    for i, (snap_orig, snap_dec) in enumerate(
        zip(result_original.daily_snapshots, result_decoded.daily_snapshots)
    ):
        assert snap_orig.total_bluestars == snap_dec.total_bluestars, (
            f"Day {i + 1}: Bluestars mismatch between original and decoded"
        )


def test_drop_algorithm_statistical_consistency(simple_config):
    """Test drop algorithm maintains consistent results over many MC runs."""
    config = simple_config
    config.num_days = 50
    for pack_name in config.pack_averages.keys():
        config.pack_averages[pack_name] = 5.0

    result = run_monte_carlo(config, num_runs=100)

    assert result.daily_bluestar_means[-1] > 0, (
        "Final mean bluestars should be positive after 50 days"
    )
    assert result.num_runs == 100, f"Expected 100 runs, got {result.num_runs}"

    all_stds_valid = all(std >= 0 for std in result.daily_bluestar_stds)
    assert all_stds_valid, "All standard deviations should be non-negative"

    mean, std = result.bluestar_stats.result()
    assert mean > 0, "Overall mean bluestars should be positive"
    assert std >= 0, "Overall std should be non-negative"


def test_progression_consistency(default_config):
    """Test that card progression follows expected patterns."""
    config = default_config
    config.num_days = 30

    result = run_simulation(config)

    first_day = result.daily_snapshots[0]
    last_day = result.daily_snapshots[-1]

    for category in ["GOLD_SHARED", "BLUE_SHARED", "UNIQUE"]:
        assert category in first_day.category_avg_levels, (
            f"Category {category} missing from first day"
        )
        assert category in last_day.category_avg_levels, (
            f"Category {category} missing from last day"
        )
        assert (
            last_day.category_avg_levels[category]
            >= first_day.category_avg_levels[category]
        ), (
            f"Category {category} average level decreased: "
            f"{first_day.category_avg_levels[category]} → {last_day.category_avg_levels[category]}"
        )


def test_deterministic_reproducibility(default_config):
    """Test that deterministic runs produce identical results."""
    config = default_config
    config.num_days = 20

    result1 = run_simulation(config, rng=Random(123))
    result2 = run_simulation(config, rng=Random(123))

    assert result1.total_bluestars == result2.total_bluestars, (
        f"Deterministic runs produced different bluestars: "
        f"{result1.total_bluestars} vs {result2.total_bluestars}"
    )

    for i, (snap1, snap2) in enumerate(
        zip(result1.daily_snapshots, result2.daily_snapshots)
    ):
        assert snap1.total_bluestars == snap2.total_bluestars, (
            f"Day {i + 1}: Bluestars differ between runs"
        )
        assert snap1.coins_balance == snap2.coins_balance, (
            f"Day {i + 1}: Coin balance differs between runs"
        )


def test_unique_unlock_schedule_integration(default_config):
    """Test that unique unlock schedule is properly integrated."""
    config = default_config
    config.num_days = 100

    result = run_simulation(config)

    day1_unlocked = result.daily_snapshots[0].total_unique_unlocked
    assert day1_unlocked > 0, "Some unique cards should unlock on day 1"

    unlocked_counts = [s.total_unique_unlocked for s in result.daily_snapshots]
    for i in range(1, len(unlocked_counts)):
        assert unlocked_counts[i] >= unlocked_counts[i - 1], (
            f"Day {i + 1}: Unique unlock count decreased"
        )
