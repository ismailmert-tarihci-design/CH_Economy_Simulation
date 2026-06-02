"""Persisted settings for the day-by-day simulator (Variant B).

The day simulator's *player type* (cohort) and *chapter gating* selections —
plus the underlying editable data tables (per-day chapter cadence and
per-chapter bluestar thresholds) — are persisted to disk here so they survive
an app restart. This is intentionally separate from `variant_b_config.json`
(the economy config): it only captures the simulator's framing knobs.

Pure Python / no Streamlit. The UI reads these as defaults on startup and
writes them back when the user edits + saves the settings bar.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List

from pydantic import BaseModel, Field

from simulation.variants.variant_b.chapter_schedule import (
    load_cohort_chapters,
    load_default_bluestar_thresholds,
)

_log = logging.getLogger(__name__)


# Calendar mode beats a fixed per-day chapter count from the cohort profile
# rather than gating on bluestars — it has no threshold table.
CALENDAR_GATING = "Calendar"


class DaySimSettings(BaseModel):
    """User-tunable, disk-persisted framing knobs for the day simulator."""

    cohort: str = "Average"
    bs_gating: str = "Non-Payer"
    paid_pass: bool = False
    auto_upgrade: bool = False
    season_length_days: int = 28

    # Per-cohort overrides for the chapters-per-day cadence. When a cohort has
    # an entry here it wins over the profile JSON; otherwise the profile is used.
    chapters_per_day_overrides: Dict[str, List[int]] = Field(default_factory=dict)

    # Per-gating overrides for the chapter bluestar-threshold curve. Keyed by
    # gating name (Non-Payer / Mid-Payer / Payer / All).
    bluestar_threshold_overrides: Dict[str, List[float]] = Field(default_factory=dict)


def _settings_path() -> Path:
    """Path to the persisted day-sim settings file."""
    return (
        Path(__file__).resolve().parents[3]
        / "data" / "defaults" / "day_sim_settings.json"
    )


def load_day_sim_settings() -> DaySimSettings:
    """Load persisted day-sim settings, or return defaults if absent/invalid."""
    path = _settings_path()
    if not path.exists():
        return DaySimSettings()
    try:
        return DaySimSettings.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        _log.warning("Failed to load day-sim settings: %s", exc)
        return DaySimSettings()


def save_day_sim_settings(settings: DaySimSettings) -> None:
    """Persist day-sim settings to disk."""
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(settings.model_dump_json(indent=2), encoding="utf-8")


def effective_chapters_per_day(settings: DaySimSettings, cohort: str) -> List[int]:
    """Resolve the chapters-per-day cadence for a cohort.

    An edited override (saved by the user) wins over the profile JSON.
    """
    override = settings.chapters_per_day_overrides.get(cohort)
    if override:
        return [int(x) for x in override]
    return load_cohort_chapters(cohort)


def effective_bluestar_thresholds(settings: DaySimSettings, gating: str) -> List[float]:
    """Resolve the per-chapter bluestar thresholds for a gating mode.

    Calendar mode has no threshold table (returns []). Otherwise an edited
    override wins over the shared defaults file.
    """
    if gating == CALENDAR_GATING:
        return []
    override = settings.bluestar_threshold_overrides.get(gating)
    if override:
        return [float(x) for x in override]
    return load_default_bluestar_thresholds(gating)
