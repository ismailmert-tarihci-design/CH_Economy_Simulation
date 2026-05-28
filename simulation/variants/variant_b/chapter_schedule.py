"""Shared cohort-chapter cadence helpers for Variant B.

The chapter-completion rhythm comes from the chosen player cohort profile
(Average / P75 / P90). Each cohort profile JSON ships a `chapters_per_day`
list. Both the day-by-day simulator UI and the big orchestrator/Monte Carlo
loop look up how many chapters to beat on a given sim day via these helpers.

Day 0 is the install / FTUE day and yields 0. Day N>=1 maps to index
`(N - 1) % len`, matching how `daily_pack_schedule` is indexed by the
orchestrator's `_get_daily_pulls`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List


def _profiles_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "data" / "profiles_variant_b"


def load_cohort_chapters(name: str) -> List[int]:
    """Read `chapters_per_day` from a Variant B cohort profile JSON.

    Returns an empty list if the profile does not exist or is missing the
    field. Falls back to `full_config.chapters_per_day` so older profile
    snapshots still work.
    """
    p = _profiles_dir() / f"{name}.json"
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    chapters = data.get("chapters_per_day")
    if not chapters:
        chapters = (data.get("full_config") or {}).get("chapters_per_day", [])
    return [int(x) for x in (chapters or [])]


def chapters_for_sim_day(chapters_per_day: List[int], sim_day: int) -> int:
    """Look up chapters to beat on the given 1-indexed sim day.

    Day 0 is the install/FTUE day and yields 0. Day N>=1 maps to index
    `(N - 1) % len`. Returns 0 when no schedule is configured.
    """
    if sim_day < 1 or not chapters_per_day:
        return 0
    return int(chapters_per_day[(sim_day - 1) % len(chapters_per_day)])


def chapters_for_bluestars(
    thresholds: List[float],
    total_bluestars: int | float,
    already_beaten: int,
) -> int:
    """How many *additional* chapters can be beaten given the player's
    current bluestars and how many they have already beaten.

    `thresholds[i]` is the bluestar amount needed to beat chapter `i + 1`.
    Returns the count of chapters whose threshold is reached but which
    have not yet been counted in `already_beaten`.

    Past the end of the table we **linearly extrapolate** the curve:
    the per-chapter step is estimated from the last two table entries
    (`step = thresholds[-1] - thresholds[-2]`), and additional chapters
    are awarded while bluestars cover that step. With a single-entry
    table or a flat tail (step <= 0) extrapolation is disabled and the
    count saturates at `len(thresholds)`.
    """
    if not thresholds:
        return 0
    bs = float(total_bluestars)
    target = 0
    for thresh in thresholds:
        if bs >= float(thresh):
            target += 1
        else:
            break

    # Linear extrapolation past the configured table.
    if target == len(thresholds) and len(thresholds) >= 2:
        step = float(thresholds[-1]) - float(thresholds[-2])
        if step > 0:
            extra = int((bs - float(thresholds[-1])) // step)
            target += max(0, extra)

    return max(0, target - int(already_beaten))


def load_default_bluestar_thresholds(cohort: str | None = None) -> List[float]:
    """Load chapter bluestar thresholds from the shared defaults file.

    Picks the requested cohort, falling back to the file's `default_cohort`
    and finally to "All". Returns an empty list if the file is missing or
    malformed.
    """
    p = (Path(__file__).resolve().parents[3]
         / "data" / "defaults" / "chapter_bluestar_thresholds.json")
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    cohorts = data.get("cohorts") or {}
    pick = cohort or data.get("default_cohort") or "All"
    table = cohorts.get(pick) or cohorts.get("All") or []
    return [float(x) for x in table]
