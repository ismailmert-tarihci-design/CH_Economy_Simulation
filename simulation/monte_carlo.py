"""
Monte Carlo simulation with Welford's online statistics algorithm.

Implements memory-efficient Monte Carlo runs using Welford's incremental
mean and variance calculations. Critical for Streamlit Cloud's 1GB memory limit.
"""

import time
import warnings
from dataclasses import dataclass
from math import sqrt
from random import Random
from typing import Any, Dict, List

import numpy as np

from simulation.models import SimConfig
from simulation.orchestrator import DailySnapshot, run_simulation


class WelfordAccumulator:
    """
    Implements Welford's online algorithm for incremental mean and variance.

    Reference: https://en.wikipedia.org/wiki/Algorithms_for_calculating_variance#Welford's_online_algorithm

    The algorithm maintains:
    - count: Number of values seen
    - mean: Running mean
    - m2: Sum of squared differences from current mean
    """

    def __init__(self) -> None:
        self.count = 0
        self.mean = 0.0
        self.m2 = 0.0

    def update(self, value: float) -> None:
        """
        Update accumulator with new value.

        Formula (EXACT - DO NOT MODIFY):
        count += 1
        delta = value - mean
        mean += delta / count
        delta2 = value - mean
        m2 += delta * delta2
        """
        self.count += 1
        delta = value - self.mean
        self.mean += delta / self.count
        delta2 = value - self.mean
        self.m2 += delta * delta2

    def result(self) -> tuple[float, float]:
        """
        Return (mean, std_dev) using Bessel's correction.

        Returns:
            Tuple of (mean, standard_deviation)
        """
        if self.count == 0:
            return 0.0, 0.0
        if self.count == 1:
            return self.mean, 0.0

        variance = self.m2 / (self.count - 1)  # Bessel's correction
        std_dev = sqrt(variance)
        return self.mean, std_dev

    def confidence_interval(self, confidence: float = 0.95) -> tuple[float, float]:
        """
        Calculate confidence interval for the mean.

        Formula: mean ± z * (std_dev / sqrt(count))
        For 95% CI: z = 1.96

        Args:
            confidence: Confidence level (default 0.95 for 95% CI)

        Returns:
            Tuple of (lower_bound, upper_bound)
        """
        if self.count == 0:
            return 0.0, 0.0

        mean, std_dev = self.result()

        # Map confidence level to z-score
        z_scores = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
        z = z_scores.get(confidence, 1.96)

        margin = z * (std_dev / sqrt(self.count))
        return mean - margin, mean + margin


class DailyAccumulators:
    """
    Tracks per-day accumulators for multiple metrics.

    For a simulation with N days, maintains N accumulators per metric type:
    - bluestar_accumulators: list of N WelfordAccumulators
    - coin_balance_accumulators: list of N WelfordAccumulators
    - category_level_accumulators: dict[category_name, list of N WelfordAccumulators]
    """

    def __init__(self, num_days: int) -> None:
        self.num_days = num_days
        self.bluestar_accumulators = [WelfordAccumulator() for _ in range(num_days)]
        self.coin_balance_accumulators = [WelfordAccumulator() for _ in range(num_days)]
        self.category_level_accumulators: Dict[str, List[WelfordAccumulator]] = {}
        self.pull_count_accumulators: Dict[str, List[WelfordAccumulator]] = {}
        self.pack_count_accumulators: Dict[str, List[WelfordAccumulator]] = {}

    def update_from_snapshot(self, day_index: int, snapshot: DailySnapshot) -> None:
        """
        Update all accumulators for a given day.

        Args:
            day_index: 0-indexed day (day=1 -> index=0)
            snapshot: DailySnapshot from run_simulation
        """
        # Update bluestar accumulator
        self.bluestar_accumulators[day_index].update(float(snapshot.total_bluestars))

        # Update coin balance accumulator
        self.coin_balance_accumulators[day_index].update(float(snapshot.coins_balance))

        # Update category level accumulators
        for category_name, avg_level in snapshot.category_avg_levels.items():
            if category_name not in self.category_level_accumulators:
                self.category_level_accumulators[category_name] = [
                    WelfordAccumulator() for _ in range(self.num_days)
                ]
            self.category_level_accumulators[category_name][day_index].update(avg_level)

        # Update pull count accumulators
        for card_type, count in snapshot.pull_counts_by_type.items():
            if card_type not in self.pull_count_accumulators:
                self.pull_count_accumulators[card_type] = [
                    WelfordAccumulator() for _ in range(self.num_days)
                ]
            self.pull_count_accumulators[card_type][day_index].update(float(count))

        # Update pack count accumulators
        for pack_name, count in snapshot.pack_counts_by_type.items():
            if pack_name not in self.pack_count_accumulators:
                self.pack_count_accumulators[pack_name] = [
                    WelfordAccumulator() for _ in range(self.num_days)
                ]
            self.pack_count_accumulators[pack_name][day_index].update(float(count))

    def finalize(self) -> Dict[str, Any]:
        """
        Extract all means and standard deviations.

        Returns:
            Dict with keys: bluestar_means, bluestar_stds, coin_balance_means,
            coin_balance_stds, category_level_means, category_level_stds
        """
        result = {}

        # Extract bluestar stats
        result["bluestar_means"] = [
            acc.result()[0] for acc in self.bluestar_accumulators
        ]
        result["bluestar_stds"] = [
            acc.result()[1] for acc in self.bluestar_accumulators
        ]

        # Extract coin balance stats
        result["coin_balance_means"] = [
            acc.result()[0] for acc in self.coin_balance_accumulators
        ]
        result["coin_balance_stds"] = [
            acc.result()[1] for acc in self.coin_balance_accumulators
        ]

        # Extract category level stats
        result["category_level_means"] = {}
        result["category_level_stds"] = {}
        for category_name, accumulators in self.category_level_accumulators.items():
            result["category_level_means"][category_name] = [
                acc.result()[0] for acc in accumulators
            ]
            result["category_level_stds"][category_name] = [
                acc.result()[1] for acc in accumulators
            ]

        # Extract pull count stats
        result["pull_count_means"] = {}
        result["pull_count_stds"] = {}
        for card_type, accumulators in self.pull_count_accumulators.items():
            result["pull_count_means"][card_type] = [
                acc.result()[0] for acc in accumulators
            ]
            result["pull_count_stds"][card_type] = [
                acc.result()[1] for acc in accumulators
            ]

        # Extract pack count stats
        result["pack_count_means"] = {}
        result["pack_count_stds"] = {}
        for pack_name, accumulators in self.pack_count_accumulators.items():
            result["pack_count_means"][pack_name] = [
                acc.result()[0] for acc in accumulators
            ]
            result["pack_count_stds"][pack_name] = [
                acc.result()[1] for acc in accumulators
            ]

        return result


@dataclass
class MCResult:
    """Results from Monte Carlo simulation runs."""

    num_runs: int
    bluestar_stats: WelfordAccumulator
    daily_bluestar_means: List[float]
    daily_bluestar_stds: List[float]
    daily_coin_balance_means: List[float]
    daily_coin_balance_stds: List[float]
    daily_category_level_means: Dict[str, List[float]]
    daily_category_level_stds: Dict[str, List[float]]
    daily_pull_count_means: Dict[str, List[float]]
    daily_pull_count_stds: Dict[str, List[float]]
    daily_pack_count_means: Dict[str, List[float]]
    daily_pack_count_stds: Dict[str, List[float]]
    completion_time: float


def run_monte_carlo(config: SimConfig, num_runs: int = 100) -> MCResult:
    """
    Run Monte Carlo simulation with Welford statistics.

    CRITICAL REQUIREMENTS:
    1. Validate: num_runs must be between 1 and 500 (hard cap)
    2. Warning: if num_runs > 200, issue UserWarning
    3. Seeded RNG: Create Random(seed=run_idx) for each run (reproducibility)
    4. Memory Safety: DO NOT store SimResult objects — extract values then discard
    5. Track timing: Record completion_time in seconds

    Args:
        config: Simulation configuration
        num_runs: Number of Monte Carlo runs (default 100)

    Returns:
        MCResult with aggregated statistics across all runs

    Raises:
        ValueError: If num_runs < 1 or num_runs > 500
    """
    # Validation
    if num_runs < 1 or num_runs > 500:
        raise ValueError(f"num_runs must be between 1 and 500, got {num_runs}")

    if num_runs > 200:
        warnings.warn(
            f"num_runs={num_runs} is large and may take significant time. "
            f"Consider using fewer runs for faster results.",
            UserWarning,
            stacklevel=2,
        )

    start_time = time.time()

    # Initialize accumulators
    final_bluestar_accumulator = WelfordAccumulator()
    daily_accumulators = DailyAccumulators(config.num_days)

    # Run Monte Carlo simulations
    for run_idx in range(1, num_runs + 1):
        rng = Random()
        rng.seed(run_idx)
        np.random.seed(run_idx)
        result = run_simulation(config, rng=rng)

        # Update final bluestar accumulator
        final_bluestar_accumulator.update(float(result.total_bluestars))

        # Update daily accumulators
        for day_idx, snapshot in enumerate(result.daily_snapshots):
            daily_accumulators.update_from_snapshot(day_idx, snapshot)

        # DO NOT STORE result — let it be garbage collected immediately

    # Finalize daily statistics
    daily_stats = daily_accumulators.finalize()

    completion_time = time.time() - start_time

    return MCResult(
        num_runs=num_runs,
        bluestar_stats=final_bluestar_accumulator,
        daily_bluestar_means=daily_stats["bluestar_means"],
        daily_bluestar_stds=daily_stats["bluestar_stds"],
        daily_coin_balance_means=daily_stats["coin_balance_means"],
        daily_coin_balance_stds=daily_stats["coin_balance_stds"],
        daily_category_level_means=daily_stats["category_level_means"],
        daily_category_level_stds=daily_stats["category_level_stds"],
        daily_pull_count_means=daily_stats["pull_count_means"],
        daily_pull_count_stds=daily_stats["pull_count_stds"],
        daily_pack_count_means=daily_stats["pack_count_means"],
        daily_pack_count_stds=daily_stats["pack_count_stds"],
        completion_time=completion_time,
    )
