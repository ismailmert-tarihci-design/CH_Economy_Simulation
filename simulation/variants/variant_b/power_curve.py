"""Bluestar -> power conversion for Variant B (Hero Card System).

Power is the cumulative product of each bluestar tier's per-bluestar
multiplier. A player who has earned `B` bluestars has

    power(B) = product over tiers t of  multiplier_t ** bluestars_of_B_in_t

where each tier covers the half-open range `(min_bluestar, max_bluestar]`.
The table is tuned (by Ismail) so this curve matches the Classic Card
System's power-per-bluestar; the day-by-day simulator uses it purely as a
read-out of `game_state.total_bluestars` — it does not feed back into game
dynamics.

Pure module: no Streamlit, no RNG.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import List, Optional


@dataclass(frozen=True)
class PowerTier:
    """One bluestar tier: bluestars in `(min_bluestar, max_bluestar]` each
    multiply power by `multiplier`."""
    tier: int
    min_bluestar: float
    max_bluestar: float
    multiplier: float


def _default_table_path() -> Path:
    return (Path(__file__).resolve().parents[3]
            / "data" / "defaults" / "variant_b_bluestar_power_table.json")


def load_power_table(path: Optional[str | Path] = None) -> List[PowerTier]:
    """Load and validate the bluestar->power tier table.

    Tiers are returned sorted by `min_bluestar` and validated to be
    contiguous (each tier starts where the previous one ended). Raises
    ValueError on a malformed/non-contiguous table.
    """
    p = Path(path) if path is not None else _default_table_path()
    data = json.loads(p.read_text(encoding="utf-8"))
    raw = data.get("tiers") or []
    tiers = [
        PowerTier(
            tier=int(t["tier"]),
            min_bluestar=float(t["min_bluestar"]),
            max_bluestar=float(t["max_bluestar"]),
            multiplier=float(t["multiplier"]),
        )
        for t in raw
    ]
    tiers.sort(key=lambda t: t.min_bluestar)
    for prev, cur in zip(tiers, tiers[1:]):
        if cur.min_bluestar != prev.max_bluestar:
            raise ValueError(
                f"Power table not contiguous: tier {prev.tier} ends at "
                f"{prev.max_bluestar} but tier {cur.tier} starts at "
                f"{cur.min_bluestar}"
            )
    return tiers


@lru_cache(maxsize=1)
def _cached_default_table() -> tuple[PowerTier, ...]:
    return tuple(load_power_table())


def power_for_bluestars(
    total_bluestars: int | float,
    table: Optional[List[PowerTier]] = None,
) -> float:
    """Return the total power multiplier for `total_bluestars` bluestars.

    Multiplies `multiplier ** count` for the bluestars of `total_bluestars`
    that fall in each tier's `(min, max]` range. Bluestars past the last
    tier are ignored (the table's final tier is expected to extend well
    beyond any reachable value).
    """
    tiers = table if table is not None else _cached_default_table()
    bs = float(total_bluestars)
    if bs <= 0:
        return 1.0
    power = 1.0
    for t in tiers:
        if bs <= t.min_bluestar:
            break
        count = min(bs, t.max_bluestar) - t.min_bluestar
        if count > 0:
            power *= t.multiplier ** count
    return power
