"""Scripted/auto-pilot day-simulator configuration for Variant B.

A `ScriptedRunConfig` records the rules an automated player follows each
day: which packs to open, how far to push the season pass, how many chapters
to beat, and how to spend Hero Tokens. The companion runner in
`scripted_runner.py` consumes this config to drive a multi-day simulation.

Configs are persisted to `data/profiles/scripted_runs/<name>.json` via the
helpers below so designers can save and re-use scenarios.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


SpendPolicy = Literal["cheapest_first", "focus_hero", "round_robin"]
ChapterGating = Literal["calendar", "bluestar"]


class ScriptedRunDay(BaseModel):
    """One day's worth of scripted events.

    A day not listed in `ScriptedRunConfig.schedule` runs the baseline
    behavior (daily packs only, if `auto_open_daily_packs` is on).
    """
    day: int = Field(description="0-based day index")
    chapters_beaten: int = Field(default=0, ge=0, description="EndOfChapter packs to open")
    season_pass_target_step: Optional[int] = Field(
        default=None,
        description="Claim free (and paid if paid_season_pass) up to this 1-based step by EOD",
    )


class ScriptedRunConfig(BaseModel):
    """Self-contained recipe for a scripted multi-day run."""
    name: str = Field(description="Display name / file slug")
    paid_season_pass: bool = Field(default=True)
    auto_open_daily_packs: bool = Field(default=True)
    token_spend_policy: SpendPolicy = Field(default="cheapest_first")
    focus_hero_id: Optional[str] = Field(
        default=None,
        description="Only used when token_spend_policy == 'focus_hero'",
    )
    chapter_gating: ChapterGating = Field(
        default="calendar",
        description="'calendar' beats a fixed per-day count; 'bluestar' beats "
                    "chapters whose bluestar threshold is reached (end of day).",
    )
    bluestar_cohort: Optional[str] = Field(
        default=None,
        description="Cohort whose chapter bluestar thresholds gate beating when "
                    "chapter_gating == 'bluestar' (e.g. 'Non-Payer').",
    )
    season_pass_steps_per_day: Optional[int] = Field(
        default=None,
        description="When set, claim exactly this many season-pass steps each "
                    "day (overrides per-day schedule targets).",
    )
    schedule: List[ScriptedRunDay] = Field(default_factory=list)


_log = logging.getLogger(__name__)


def _scripted_runs_dir() -> Path:
    return (
        Path(__file__).resolve().parent.parent.parent.parent
        / "data" / "profiles" / "scripted_runs"
    )


def _safe_slug(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name.strip()) or "untitled"


def save_scripted_run(cfg: ScriptedRunConfig) -> Path:
    """Persist `cfg` to data/profiles/scripted_runs/<slug>.json. Returns the path."""
    out = _scripted_runs_dir() / f"{_safe_slug(cfg.name)}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(cfg.model_dump_json(indent=2), encoding="utf-8")
    return out


def load_scripted_run(name: str) -> Optional[ScriptedRunConfig]:
    """Load a saved scripted run by name (or slug). Returns None if not found."""
    path = _scripted_runs_dir() / f"{_safe_slug(name)}.json"
    if not path.exists():
        return None
    try:
        return ScriptedRunConfig.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover — surfaces in UI as a warning
        _log.warning("Failed to load scripted run %s: %s", name, exc)
        return None


def list_scripted_runs() -> List[str]:
    """List the saved scripted-run names (sorted)."""
    d = _scripted_runs_dir()
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob("*.json"))


def delete_scripted_run(name: str) -> bool:
    """Delete a saved scripted run. Returns True if removed."""
    path = _scripted_runs_dir() / f"{_safe_slug(name)}.json"
    if path.exists():
        path.unlink()
        return True
    return False
