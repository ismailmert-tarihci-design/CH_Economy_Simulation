"""Hero Token demand analysis.

Answers: "How many Hero Tokens does a player need each day, across the whole
game, if they buy every Hero Path (skill-tree) node they have unlocked?"

The demand is supply-independent: a node becomes *purchasable* the day its
hero-level gate is reached. We run the normal Variant B simulation with
`unlimited_hero_tokens=True` so node activation is driven purely by hero level
(and so all unlockable cards come online on schedule, matching the
"buys everything" progression). For each day we record:

  - daily_demand      : token cost of nodes that became purchasable that day
  - cumulative_demand : running total (what you'd have spent to date)
  - heroes_unlocked   : how many heroes are live
  - per-hero levels    : so you can see how fast a single hero progresses

Usage:
    python -m tools.hero_token_demand                 # default config, seed 42
    python -m tools.hero_token_demand --profile P90
    python -m tools.hero_token_demand --seed 7 --csv out.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from random import Random

from simulation.variants.variant_b.config_loader import (
    load_defaults,
    load_vb_profile,
)
from simulation.variants.variant_b.models import HeroCardConfig
from simulation.variants.variant_b.orchestrator import run_simulation


# Days Ivan-style milestones are reported at (clamped to the run length).
MILESTONE_DAYS = [1, 7, 14, 30, 60, 70, 90, 120, 180, 250, 365, 500, 730]


def load_config(profile: str | None) -> HeroCardConfig:
    if profile:
        prof = load_vb_profile(profile)
        if prof.full_config is None:
            raise SystemExit(f"Profile '{profile}' has no full_config to load.")
        return HeroCardConfig.model_validate(prof.full_config)
    return load_defaults()


def build_rows(result) -> list[dict]:
    rows: list[dict] = []
    cumulative = 0
    for snap in result.daily_snapshots:
        cumulative += snap.hero_token_demand_today
        heroes_unlocked = len(snap.hero_levels)
        rows.append({
            "day": snap.day,
            "heroes_unlocked": heroes_unlocked,
            "daily_demand": snap.hero_token_demand_today,
            "cumulative_demand": cumulative,
            "demand_per_hero_avg": round(cumulative / heroes_unlocked, 1) if heroes_unlocked else 0,
            "hero_levels": dict(sorted(snap.hero_levels.items())),
            "tokens_received_today": snap.hero_tokens_received,
        })
    return rows


def print_milestones(rows: list[dict], num_days: int) -> None:
    by_day = {r["day"]: r for r in rows}
    print()
    print("Hero Token demand — buy-everything-you've-unlocked path")
    print("=" * 78)
    print(f"{'Day':>4} {'Heroes':>7} {'DailyNeed':>10} {'CumNeed':>10} {'Cum/Hero':>9}  HeroLevels")
    print("-" * 78)
    for d in MILESTONE_DAYS:
        if d > num_days:
            continue
        r = by_day.get(d)
        if not r:
            continue
        # Show the levels of the heroes that are live, sorted high->low.
        lvls = sorted(r["hero_levels"].values(), reverse=True)
        lvl_str = "/".join(str(x) for x in lvls)
        print(f"{r['day']:>4} {r['heroes_unlocked']:>7} {r['daily_demand']:>10,} "
              f"{r['cumulative_demand']:>10,} {r['demand_per_hero_avg']:>9,}  {lvl_str}")
    print("-" * 78)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--profile", default=None, help="Variant B profile name (e.g. Average, P75, P90). Default: built-in defaults.")
    ap.add_argument("--seed", type=int, default=42, help="RNG seed (default 42). Use --deterministic for no RNG.")
    ap.add_argument("--deterministic", action="store_true", help="Run with rng=None (rounds pack counts; understates pulls).")
    ap.add_argument("--csv", default=None, help="Write the full per-day table to this CSV path.")
    args = ap.parse_args(argv)

    config = load_config(args.profile)
    config.unlimited_hero_tokens = True

    rng = None if args.deterministic else Random(args.seed)
    result = run_simulation(config, rng=rng)
    rows = build_rows(result)

    print_milestones(rows, config.num_days)
    print(f"\nTotal demand to buy every unlocked node over {config.num_days} days: "
          f"{result.total_hero_token_demand:,} tokens")
    print(f"Average across the run: {result.total_hero_token_demand / config.num_days:,.0f} tokens/day")
    print("(Demand is supply-independent — compare against your modeled token "
          "income separately to size Hero Booster contents.)")

    if args.csv:
        with open(args.csv, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["day", "heroes_unlocked", "daily_demand", "cumulative_demand",
                        "demand_per_hero_avg", "tokens_received_today", "hero_levels"])
            for r in rows:
                lvl_str = ";".join(f"{h}:{lv}" for h, lv in r["hero_levels"].items())
                w.writerow([r["day"], r["heroes_unlocked"], r["daily_demand"],
                            r["cumulative_demand"], r["demand_per_hero_avg"],
                            r["tokens_received_today"], lvl_str])
        print(f"\nWrote per-day table to {args.csv}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
