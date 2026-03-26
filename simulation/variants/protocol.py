"""Protocol definitions for the variant framework.

Defines structural contracts that every variant must satisfy so that
Monte Carlo, comparison dashboards, and the UI dispatch layer can work
with any variant without importing its concrete types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol, runtime_checkable
from random import Random


@runtime_checkable
class ConfigProtocol(Protocol):
    """Minimum config fields every variant must expose."""

    num_days: int
    initial_coins: int
    initial_bluestars: int

    def model_dump_json(self, **kwargs: Any) -> str: ...


@runtime_checkable
class DailySnapshotProtocol(Protocol):
    """Common daily snapshot fields for MC aggregation and comparison."""

    day: int
    total_bluestars: int
    bluestars_earned_today: int
    coins_balance: int
    coins_earned_today: int
    coins_spent_today: int
    category_avg_levels: Dict[str, float]
    pull_counts_by_type: Dict[str, int]
    pack_counts_by_type: Dict[str, int]


@runtime_checkable
class SimResultProtocol(Protocol):
    """Common result fields every variant must expose."""

    daily_snapshots: List[Any]
    total_bluestars: int
    total_coins_earned: int
    total_coins_spent: int


@dataclass
class VariantInfo:
    """Registration descriptor for a simulation variant."""

    variant_id: str
    display_name: str
    description: str

    # Core callables
    run_simulation: Callable[..., Any]  # (config, rng?) -> SimResultProtocol
    load_defaults: Callable[[], Any]  # () -> ConfigProtocol

    # Type references (for deserialization, UI dispatch, etc.)
    config_class: type
    result_class: type

    # Extra snapshot fields this variant provides beyond the protocol
    extra_snapshot_fields: List[str] = field(default_factory=list)
