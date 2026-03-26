"""Comparison utilities for overlaying results from multiple variants.

Extracts common protocol fields (bluestars, coins, card levels) from any
variant's results for side-by-side charting.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


def extract_common_metrics(
    result: Any, mode: str
) -> Dict[str, Any]:
    """Extract protocol-level metrics from any variant's result.

    Returns dict with keys: days, bluestars, coins_balance,
    category_avg_levels (dict of lists), plus mode-specific fields.
    """
    if mode == "deterministic":
        snapshots = result.daily_snapshots
        return {
            "days": [s.day for s in snapshots],
            "bluestars": [s.total_bluestars for s in snapshots],
            "coins_balance": [s.coins_balance for s in snapshots],
            "category_avg_levels": _extract_category_levels(snapshots),
            "total_bluestars": result.total_bluestars,
            "total_coins_earned": result.total_coins_earned,
        }
    else:
        return {
            "days": list(range(1, len(result.daily_bluestar_means) + 1)),
            "bluestar_means": result.daily_bluestar_means,
            "bluestar_stds": result.daily_bluestar_stds,
            "coin_balance_means": result.daily_coin_balance_means,
            "total_bluestars_mean": result.bluestar_stats.result()[0],
            "num_runs": result.num_runs,
        }


def _extract_category_levels(snapshots: list) -> Dict[str, List[float]]:
    """Extract per-category average levels across days."""
    if not snapshots:
        return {}
    all_cats = set()
    for s in snapshots:
        all_cats.update(s.category_avg_levels.keys())
    result = {}
    for cat in sorted(all_cats):
        result[cat] = [s.category_avg_levels.get(cat, 0.0) for s in snapshots]
    return result
