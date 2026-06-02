"""
Monte Carlo simulation with Welford's online statistics algorithm.

Implements memory-efficient Monte Carlo runs using Welford's incremental
mean and variance calculations. Critical for Streamlit Cloud's 1GB memory limit.
"""

import time
import warnings
from dataclasses import dataclass, field
from math import sqrt
from random import Random
from typing import Any, Dict, List

# Upgrade / bluestar-source breakdown keys. "type_color" where type is the
# upgrade origin (HERO card vs SHARED card) and color is the card rarity
# (GOLD / BLUE / GRAY). Fixed set so per-day means are computed over every
# run (days with no upgrades of a key contribute a 0, not a missing sample).
UPGRADE_BREAKDOWN_KEYS = [
    "HERO_GOLD", "HERO_BLUE", "HERO_GRAY",
    "SHARED_GOLD", "SHARED_BLUE", "SHARED_GRAY",
]
# Bluestar sources = the same upgrade buckets plus direct premium-pack grants.
BLUESTAR_SOURCE_KEYS = UPGRADE_BREAKDOWN_KEYS + ["PREMIUM_PACK"]


def _breakdown_keys_from_snapshot(snapshot: Any) -> tuple[dict, dict, int]:
    """Parse a daily snapshot's upgrade events into per-key counts and bluestars.

    Returns (upgrade_counts, bluestars_from_upgrades, premium_bluestars) where
    the first two are dicts keyed by UPGRADE_BREAKDOWN_KEYS.
    """
    counts: Dict[str, int] = {}
    bluestars: Dict[str, int] = {}
    for evt in getattr(snapshot, "upgrades_today", None) or []:
        if "category" in evt:  # shared-card upgrade: GOLD_SHARED / BLUE_SHARED / ...
            color = str(evt.get("category", "")).replace("_SHARED", "")
            key = f"SHARED_{color}"
        else:  # hero-card upgrade
            color = str(evt.get("rarity", ""))
            key = f"HERO_{color}"
        if key not in UPGRADE_BREAKDOWN_KEYS:
            continue
        counts[key] = counts.get(key, 0) + 1
        bluestars[key] = bluestars.get(key, 0) + int(evt.get("bluestars_earned", 0))
    premium = int(getattr(snapshot, "premium_bluestars_today", 0) or 0)
    return counts, bluestars, premium


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
        # Per-hero per-day accumulators (Variant B only — populated lazily when
        # snapshots carry a `hero_states` field). Keyed by hero_id -> list of
        # per-day WelfordAccumulators, one nested dict per scalar metric.
        self.hero_level_accumulators: Dict[str, List[WelfordAccumulator]] = {}
        self.hero_xp_accumulators: Dict[str, List[WelfordAccumulator]] = {}
        self.hero_joker_accumulators: Dict[str, List[WelfordAccumulator]] = {}
        self.hero_total_cards_accumulators: Dict[str, List[WelfordAccumulator]] = {}
        # Per-hero pet/gear accumulators. Pet uses scalar `pet_level`; gear
        # aggregates `gear_total_level` (sum of all slot levels) — a single
        # scalar is enough to drive the dashboard chart without ballooning the
        # MCResult shape into per-slot series.
        self.hero_pet_level_accumulators: Dict[str, List[WelfordAccumulator]] = {}
        self.hero_gear_total_level_accumulators: Dict[str, List[WelfordAccumulator]] = {}
        # Upgrade & bluestar-source breakdowns (Variant B). Fixed key sets so
        # every run contributes a sample (0 when absent) to every per-day bucket.
        self.upgrade_count_accumulators: Dict[str, List[WelfordAccumulator]] = {
            key: [WelfordAccumulator() for _ in range(num_days)]
            for key in UPGRADE_BREAKDOWN_KEYS
        }
        self.bluestar_source_accumulators: Dict[str, List[WelfordAccumulator]] = {
            key: [WelfordAccumulator() for _ in range(num_days)]
            for key in BLUESTAR_SOURCE_KEYS
        }

    def update_from_snapshot(self, day_index: int, snapshot: Any) -> None:
        """
        Update all accumulators for a given day.

        Args:
            day_index: 0-indexed day (day=1 -> index=0)
            snapshot: Any object satisfying DailySnapshotProtocol
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

        # Per-hero accumulators (Variant B). Duck-typed: only fires when the
        # snapshot carries a `hero_states` mapping. Variant A snapshots have
        # no such attribute, so this is a no-op there.
        hero_states = getattr(snapshot, "hero_states", None)
        if hero_states:
            for hero_id, hero_snap in hero_states.items():
                for table in (
                    self.hero_level_accumulators,
                    self.hero_xp_accumulators,
                    self.hero_joker_accumulators,
                    self.hero_total_cards_accumulators,
                    self.hero_pet_level_accumulators,
                    self.hero_gear_total_level_accumulators,
                ):
                    if hero_id not in table:
                        table[hero_id] = [
                            WelfordAccumulator() for _ in range(self.num_days)
                        ]
                self.hero_level_accumulators[hero_id][day_index].update(
                    float(getattr(hero_snap, "level", 0))
                )
                self.hero_xp_accumulators[hero_id][day_index].update(
                    float(getattr(hero_snap, "xp", 0))
                )
                self.hero_joker_accumulators[hero_id][day_index].update(
                    float(getattr(hero_snap, "joker_count", 0))
                )
                self.hero_total_cards_accumulators[hero_id][day_index].update(
                    float(getattr(hero_snap, "total_cards", 0))
                )
                # Pet level (scalar) + gear total level (sum across slots).
                # `getattr` keeps this no-op when the snapshot type pre-dates
                # the pet/gear fields.
                self.hero_pet_level_accumulators[hero_id][day_index].update(
                    float(getattr(hero_snap, "pet_level", 0))
                )
                self.hero_gear_total_level_accumulators[hero_id][day_index].update(
                    float(getattr(hero_snap, "gear_total_level", 0))
                )

        # Upgrade / bluestar-source breakdowns. Update every fixed key with the
        # day's total (0 when no events of that bucket) so means stay unbiased.
        counts, upgrade_bluestars, premium_bluestars = _breakdown_keys_from_snapshot(snapshot)
        for key in UPGRADE_BREAKDOWN_KEYS:
            self.upgrade_count_accumulators[key][day_index].update(float(counts.get(key, 0)))
            self.bluestar_source_accumulators[key][day_index].update(
                float(upgrade_bluestars.get(key, 0))
            )
        self.bluestar_source_accumulators["PREMIUM_PACK"][day_index].update(
            float(premium_bluestars)
        )

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

        # Extract per-hero stats (variant B). Empty dicts when MC ran against a
        # variant whose snapshots don't carry `hero_states`.
        for key, source in (
            ("hero_level", self.hero_level_accumulators),
            ("hero_xp", self.hero_xp_accumulators),
            ("hero_joker", self.hero_joker_accumulators),
            ("hero_total_cards", self.hero_total_cards_accumulators),
            ("hero_pet_level", self.hero_pet_level_accumulators),
            ("hero_gear_total_level", self.hero_gear_total_level_accumulators),
        ):
            result[f"{key}_means"] = {}
            result[f"{key}_stds"] = {}
            for hero_id, accumulators in source.items():
                result[f"{key}_means"][hero_id] = [
                    acc.result()[0] for acc in accumulators
                ]
                result[f"{key}_stds"][hero_id] = [
                    acc.result()[1] for acc in accumulators
                ]

        # Upgrade count + bluestar-source breakdowns.
        result["upgrade_count_means"] = {}
        result["upgrade_count_stds"] = {}
        for key, accumulators in self.upgrade_count_accumulators.items():
            result["upgrade_count_means"][key] = [acc.result()[0] for acc in accumulators]
            result["upgrade_count_stds"][key] = [acc.result()[1] for acc in accumulators]

        result["bluestar_source_means"] = {}
        result["bluestar_source_stds"] = {}
        for key, accumulators in self.bluestar_source_accumulators.items():
            result["bluestar_source_means"][key] = [acc.result()[0] for acc in accumulators]
            result["bluestar_source_stds"][key] = [acc.result()[1] for acc in accumulators]

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
    # Per-hero per-day means/stds (Variant B only — empty for other variants).
    # Keyed by hero_id -> list-of-num_days floats.
    daily_hero_level_means: Dict[str, List[float]] = field(default_factory=dict)
    daily_hero_level_stds: Dict[str, List[float]] = field(default_factory=dict)
    daily_hero_xp_means: Dict[str, List[float]] = field(default_factory=dict)
    daily_hero_xp_stds: Dict[str, List[float]] = field(default_factory=dict)
    daily_hero_joker_means: Dict[str, List[float]] = field(default_factory=dict)
    daily_hero_joker_stds: Dict[str, List[float]] = field(default_factory=dict)
    daily_hero_total_cards_means: Dict[str, List[float]] = field(default_factory=dict)
    daily_hero_total_cards_stds: Dict[str, List[float]] = field(default_factory=dict)
    # Per-hero pet/gear progression (Variant B only).
    daily_hero_pet_level_means: Dict[str, List[float]] = field(default_factory=dict)
    daily_hero_pet_level_stds: Dict[str, List[float]] = field(default_factory=dict)
    daily_hero_gear_total_level_means: Dict[str, List[float]] = field(default_factory=dict)
    daily_hero_gear_total_level_stds: Dict[str, List[float]] = field(default_factory=dict)
    # Upgrade-count + bluestar-source breakdowns by type+color (Variant B).
    # Keyed by UPGRADE_BREAKDOWN_KEYS / BLUESTAR_SOURCE_KEYS -> per-day floats.
    daily_upgrade_count_means: Dict[str, List[float]] = field(default_factory=dict)
    daily_upgrade_count_stds: Dict[str, List[float]] = field(default_factory=dict)
    daily_bluestar_source_means: Dict[str, List[float]] = field(default_factory=dict)
    daily_bluestar_source_stds: Dict[str, List[float]] = field(default_factory=dict)
    completion_time: float = 0.0


def run_monte_carlo(
    config: Any,
    num_runs: int = 100,
    run_fn: Any = None,
) -> MCResult:
    """
    Run Monte Carlo simulation with Welford statistics.

    CRITICAL REQUIREMENTS:
    1. Validate: num_runs must be between 1 and 500 (hard cap)
    2. Warning: if num_runs > 200, issue UserWarning
    3. Seeded RNG: Create Random(seed=run_idx) for each run (reproducibility)
    4. Memory Safety: DO NOT store SimResult objects — extract values then discard
    5. Track timing: Record completion_time in seconds

    Args:
        config: Simulation configuration (any ConfigProtocol)
        num_runs: Number of Monte Carlo runs (default 100)
        run_fn: Simulation callable (config, rng=) -> SimResultProtocol.
                Required — callers pass the active variant's run_simulation.

    Returns:
        MCResult with aggregated statistics across all runs

    Raises:
        ValueError: If num_runs < 1 or num_runs > 500, or run_fn is None
    """
    if run_fn is None:
        raise ValueError("run_fn is required (pass the variant's run_simulation)")
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
        rng = Random(run_idx)
        result = run_fn(config, rng=rng)

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
        daily_hero_level_means=daily_stats["hero_level_means"],
        daily_hero_level_stds=daily_stats["hero_level_stds"],
        daily_hero_xp_means=daily_stats["hero_xp_means"],
        daily_hero_xp_stds=daily_stats["hero_xp_stds"],
        daily_hero_joker_means=daily_stats["hero_joker_means"],
        daily_hero_joker_stds=daily_stats["hero_joker_stds"],
        daily_hero_total_cards_means=daily_stats["hero_total_cards_means"],
        daily_hero_total_cards_stds=daily_stats["hero_total_cards_stds"],
        daily_hero_pet_level_means=daily_stats["hero_pet_level_means"],
        daily_hero_pet_level_stds=daily_stats["hero_pet_level_stds"],
        daily_hero_gear_total_level_means=daily_stats["hero_gear_total_level_means"],
        daily_hero_gear_total_level_stds=daily_stats["hero_gear_total_level_stds"],
        daily_upgrade_count_means=daily_stats["upgrade_count_means"],
        daily_upgrade_count_stds=daily_stats["upgrade_count_stds"],
        daily_bluestar_source_means=daily_stats["bluestar_source_means"],
        daily_bluestar_source_stds=daily_stats["bluestar_source_stds"],
        completion_time=completion_time,
    )
