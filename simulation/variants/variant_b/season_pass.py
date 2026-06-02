"""Season Pass — Variant B (Hero Card System).

Hardcoded 90-step reward table for the day-by-day interactive simulator.
Each step has a PurpleStar requirement (displayed but not enforced), plus
a Free reward and a Paid reward. When the user advances a step:

  - Free reward is always applied.
  - Paid reward is applied only when the paid-pass toggle is ON.

Rewards mutate either the authoritative HeroCardGameState (coins) or a
dict of side counters owned by the day simulator (everything else, including
unopened-pack counts that the user later opens manually).
"""

from __future__ import annotations

from random import Random
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel

from simulation.variants.variant_b.models import HeroCardConfig, HeroCardGameState


class SeasonPassReward(BaseModel):
    reward_type: str
    amount: int


class SeasonPassStep(BaseModel):
    step: int
    required_purple_star: int
    free: SeasonPassReward
    paid: SeasonPassReward


def _r(t: str, a: int) -> SeasonPassReward:
    return SeasonPassReward(reward_type=t, amount=a)


SEASON_PASS_TABLE: List[SeasonPassStep] = [
    SeasonPassStep(step=1,  required_purple_star=0,    free=_r("StandardPackT1", 1),  paid=_r("StandardPackT4", 1)),
    SeasonPassStep(step=2,  required_purple_star=16,   free=_r("StandardPackT1", 1),  paid=_r("S-Stone", 1)),
    SeasonPassStep(step=3,  required_purple_star=32,   free=_r("Diamond", 5),         paid=_r("Diamond", 25)),
    SeasonPassStep(step=4,  required_purple_star=48,   free=_r("StandardPackT1", 1),  paid=_r("StandardPackT2", 1)),
    SeasonPassStep(step=5,  required_purple_star=64,   free=_r("Coins", 500),         paid=_r("Coins", 1000)),
    SeasonPassStep(step=6,  required_purple_star=80,   free=_r("StandardPackT2", 1),  paid=_r("StandardPackT3", 1)),
    SeasonPassStep(step=7,  required_purple_star=96,   free=_r("Diamond", 5),         paid=_r("Diamond", 25)),
    SeasonPassStep(step=8,  required_purple_star=112,  free=_r("StandardPackT1", 1),  paid=_r("StandardPackT1", 1)),
    SeasonPassStep(step=9,  required_purple_star=128,  free=_r("Coins", 800),         paid=_r("Coins", 1600)),
    SeasonPassStep(step=10, required_purple_star=144,  free=_r("StandardPackT2", 1),  paid=_r("StandardPackT3", 1)),
    SeasonPassStep(step=11, required_purple_star=160,  free=_r("Coins", 600),         paid=_r("Coins", 1200)),
    SeasonPassStep(step=12, required_purple_star=176,  free=_r("StandardPackT1", 1),  paid=_r("StandardPackT1", 1)),
    SeasonPassStep(step=13, required_purple_star=192,  free=_r("Diamond", 5),         paid=_r("Diamond", 25)),
    SeasonPassStep(step=14, required_purple_star=208,  free=_r("StandardPackT1", 1),  paid=_r("StandardPackT1", 1)),
    SeasonPassStep(step=15, required_purple_star=224,  free=_r("Coins", 500),         paid=_r("Coins", 1000)),
    SeasonPassStep(step=16, required_purple_star=240,  free=_r("StandardPackT2", 1),  paid=_r("StandardPackT3", 1)),
    SeasonPassStep(step=17, required_purple_star=256,  free=_r("Diamond", 5),         paid=_r("Diamond", 25)),
    SeasonPassStep(step=18, required_purple_star=272,  free=_r("StandardPackT1", 1),  paid=_r("StandardPackT1", 1)),
    SeasonPassStep(step=19, required_purple_star=288,  free=_r("Coins", 800),         paid=_r("Coins", 1600)),
    SeasonPassStep(step=20, required_purple_star=304,  free=_r("GearPack", 1),        paid=_r("GearPack", 1)),
    SeasonPassStep(step=21, required_purple_star=320,  free=_r("Coins", 600),         paid=_r("Coins", 1200)),
    SeasonPassStep(step=22, required_purple_star=336,  free=_r("StandardPackT1", 1),  paid=_r("StandardPackT1", 1)),
    SeasonPassStep(step=23, required_purple_star=352,  free=_r("Diamond", 5),         paid=_r("Diamond", 25)),
    SeasonPassStep(step=24, required_purple_star=368,  free=_r("StandardPackT1", 1),  paid=_r("StandardPackT1", 1)),
    SeasonPassStep(step=25, required_purple_star=384,  free=_r("Coins", 500),         paid=_r("Coins", 1000)),
    SeasonPassStep(step=26, required_purple_star=400,  free=_r("StandardPackT1", 1),  paid=_r("StandardPackT2", 1)),
    SeasonPassStep(step=27, required_purple_star=416,  free=_r("Diamond", 5),         paid=_r("Diamond", 25)),
    SeasonPassStep(step=28, required_purple_star=432,  free=_r("StandardPackT1", 1),  paid=_r("StandardPackT1", 1)),
    SeasonPassStep(step=29, required_purple_star=448,  free=_r("RandomGear", 1),      paid=_r("RandomGear", 2)),
    SeasonPassStep(step=30, required_purple_star=464,  free=_r("StandardPackT2", 1),  paid=_r("StandardPackT3", 1)),
    SeasonPassStep(step=31, required_purple_star=480,  free=_r("RandomDesign", 30),   paid=_r("RandomDesign", 30)),
    SeasonPassStep(step=32, required_purple_star=496,  free=_r("StandardPackT1", 1),  paid=_r("StandardPackT1", 1)),
    SeasonPassStep(step=33, required_purple_star=512,  free=_r("Diamond", 5),         paid=_r("Diamond", 25)),
    SeasonPassStep(step=34, required_purple_star=528,  free=_r("StandardPackT1", 1),  paid=_r("StandardPackT1", 1)),
    SeasonPassStep(step=35, required_purple_star=544,  free=_r("Coins", 500),         paid=_r("Coins", 1000)),
    SeasonPassStep(step=36, required_purple_star=560,  free=_r("StandardPackT2", 1),  paid=_r("StandardPackT2", 1)),
    SeasonPassStep(step=37, required_purple_star=576,  free=_r("RandomDesign", 30),   paid=_r("RandomDesign", 60)),
    SeasonPassStep(step=38, required_purple_star=592,  free=_r("StandardPackT1", 1),  paid=_r("StandardPackT1", 1)),
    SeasonPassStep(step=39, required_purple_star=608,  free=_r("StandardPackT1", 1),  paid=_r("StandardPackT3", 1)),
    SeasonPassStep(step=40, required_purple_star=624,  free=_r("StandardPackT3", 1),  paid=_r("StandardPackT3", 1)),
    SeasonPassStep(step=41, required_purple_star=640,  free=_r("Coins", 600),         paid=_r("Coins", 1200)),
    SeasonPassStep(step=42, required_purple_star=656,  free=_r("StandardPackT1", 1),  paid=_r("StandardPackT1", 1)),
    SeasonPassStep(step=43, required_purple_star=672,  free=_r("Diamond", 5),         paid=_r("Diamond", 25)),
    SeasonPassStep(step=44, required_purple_star=688,  free=_r("StandardPackT1", 1),  paid=_r("StandardPackT1", 1)),
    SeasonPassStep(step=45, required_purple_star=704,  free=_r("SpiritStone", 100),   paid=_r("SpiritStone", 100)),
    SeasonPassStep(step=46, required_purple_star=720,  free=_r("StandardPackT2", 1),  paid=_r("StandardPackT2", 1)),
    SeasonPassStep(step=47, required_purple_star=736,  free=_r("RandomDesign", 30),   paid=_r("RandomDesign", 60)),
    SeasonPassStep(step=48, required_purple_star=752,  free=_r("StandardPackT1", 1),  paid=_r("StandardPackT1", 1)),
    SeasonPassStep(step=49, required_purple_star=768,  free=_r("HeroTokens", 25),     paid=_r("HeroTokens", 300)),
    SeasonPassStep(step=50, required_purple_star=784,  free=_r("StandardPackT2", 1),  paid=_r("S-Stone", 1)),
    SeasonPassStep(step=51, required_purple_star=800,  free=_r("HeroTokens", 300),    paid=_r("HeroTokens", 300)),
    SeasonPassStep(step=52, required_purple_star=816,  free=_r("RandomGear", 1),      paid=_r("RandomGear", 2)),
    SeasonPassStep(step=53, required_purple_star=832,  free=_r("Diamond", 5),         paid=_r("Diamond", 25)),
    SeasonPassStep(step=54, required_purple_star=848,  free=_r("StandardPackT1", 1),  paid=_r("StandardPackT1", 1)),
    SeasonPassStep(step=55, required_purple_star=864,  free=_r("SpiritStone", 100),   paid=_r("SpiritStone", 100)),
    SeasonPassStep(step=56, required_purple_star=880,  free=_r("StandardPackT2", 1),  paid=_r("StandardPackT2", 1)),
    SeasonPassStep(step=57, required_purple_star=896,  free=_r("RandomDesign", 30),   paid=_r("RandomDesign", 60)),
    SeasonPassStep(step=58, required_purple_star=912,  free=_r("StandardPackT1", 1),  paid=_r("StandardPackT1", 1)),
    SeasonPassStep(step=59, required_purple_star=928,  free=_r("HeroTokens", 300),    paid=_r("HeroTokens", 300)),
    SeasonPassStep(step=60, required_purple_star=944,  free=_r("StandardPackT2", 1),  paid=_r("StandardPackT3", 1)),
    SeasonPassStep(step=61, required_purple_star=960,  free=_r("RandomDesign", 50),   paid=_r("RandomDesign", 50)),
    SeasonPassStep(step=62, required_purple_star=976,  free=_r("StandardPackT1", 1),  paid=_r("StandardPackT1", 1)),
    SeasonPassStep(step=63, required_purple_star=992,  free=_r("Diamond", 10),        paid=_r("Diamond", 25)),
    SeasonPassStep(step=64, required_purple_star=1008, free=_r("StandardPackT1", 1),  paid=_r("StandardPackT1", 1)),
    SeasonPassStep(step=65, required_purple_star=1024, free=_r("SpiritStone", 100),   paid=_r("SpiritStone", 200)),
    SeasonPassStep(step=66, required_purple_star=1040, free=_r("PetFood", 500),       paid=_r("PetFood", 1000)),
    SeasonPassStep(step=67, required_purple_star=1056, free=_r("RandomDesign", 30),   paid=_r("PetEgg", 50)),
    SeasonPassStep(step=68, required_purple_star=1072, free=_r("StandardPackT1", 1),  paid=_r("StandardPackT1", 1)),
    SeasonPassStep(step=69, required_purple_star=1088, free=_r("HeroTokens", 300),    paid=_r("HeroTokens", 300)),
    SeasonPassStep(step=70, required_purple_star=1104, free=_r("StandardPackT3", 1),  paid=_r("StandardPackT4", 1)),
    SeasonPassStep(step=71, required_purple_star=1120, free=_r("HeroTokens", 25),     paid=_r("HeroTokens", 100)),
    SeasonPassStep(step=72, required_purple_star=1136, free=_r("StandardPackT1", 1),  paid=_r("StandardPackT1", 1)),
    SeasonPassStep(step=73, required_purple_star=1152, free=_r("Diamond", 5),         paid=_r("Diamond", 25)),
    SeasonPassStep(step=74, required_purple_star=1168, free=_r("StandardPackT1", 1),  paid=_r("StandardPackT1", 1)),
    SeasonPassStep(step=75, required_purple_star=1184, free=_r("SpiritStone", 100),   paid=_r("SpiritStone", 100)),
    SeasonPassStep(step=76, required_purple_star=1200, free=_r("PetFood", 500),       paid=_r("PetFood", 1000)),
    SeasonPassStep(step=77, required_purple_star=1216, free=_r("RandomDesign", 30),   paid=_r("PetEgg", 50)),
    SeasonPassStep(step=78, required_purple_star=1232, free=_r("StandardPackT1", 1),  paid=_r("StandardPackT1", 1)),
    SeasonPassStep(step=79, required_purple_star=1248, free=_r("HeroTokens", 300),    paid=_r("HeroTokens", 300)),
    SeasonPassStep(step=80, required_purple_star=1264, free=_r("StandardPackT3", 1),  paid=_r("S-Stone", 1)),
    SeasonPassStep(step=81, required_purple_star=1280, free=_r("SpiritStone", 300),   paid=_r("SpiritStone", 600)),
    SeasonPassStep(step=82, required_purple_star=1296, free=_r("StandardPackT1", 1),  paid=_r("StandardPackT1", 1)),
    SeasonPassStep(step=83, required_purple_star=1312, free=_r("Diamond", 5),         paid=_r("Diamond", 25)),
    SeasonPassStep(step=84, required_purple_star=1328, free=_r("StandardPackT1", 1),  paid=_r("StandardPackT1", 1)),
    SeasonPassStep(step=85, required_purple_star=1344, free=_r("HeroPack", 1),        paid=_r("HeroPack", 1)),
    SeasonPassStep(step=86, required_purple_star=1360, free=_r("HeroTokens", 50),     paid=_r("HeroTokens", 100)),
    SeasonPassStep(step=87, required_purple_star=1376, free=_r("PetPack", 1),         paid=_r("Everstone", 1)),
    SeasonPassStep(step=88, required_purple_star=1392, free=_r("StandardPackT1", 1),  paid=_r("StandardPackT1", 1)),
    SeasonPassStep(step=89, required_purple_star=1408, free=_r("GearPack", 1),        paid=_r("GearPack", 1)),
    SeasonPassStep(step=90, required_purple_star=1424, free=_r("S-Stone", 1),         paid=_r("StandardPackT4", 1)),
]


# Reward types that go into extras["unopened_packs"][name] (openable packs)
_PACK_REWARD_TYPES = {
    "StandardPackT1", "StandardPackT2", "StandardPackT3", "StandardPackT4", "StandardPackT5",
    "HeroPack", "PetPack", "GearPack", "EndOfChapterPack",
}

# Season-pass reward type → canonical bonus_items key in HeroCardGameState.
# Note: spec uses "Diamond" (singular) for season pass, normalized to "Diamonds".
_BONUS_KEY_MAP: Dict[str, str] = {
    "HeroTokens":   "HeroTokens",
    "Diamond":      "Diamonds",
    "S-Stone":      "S-Stone",
    "SpiritStone":  "SpiritStone",
    "RandomDesign": "RandomDesign",
    "RandomGear":   "RandomGear",
    "PetFood":      "PetFood",
    "PetEgg":       "PetEgg",
    "Everstone":    "Everstone",
}


def _apply_reward(
    reward: SeasonPassReward,
    game_state: HeroCardGameState,
    extras: Dict[str, Any],
    config: Optional[HeroCardConfig],
    rng: Optional[Random],
    opened_packs: List[Dict[str, Any]],
    skip_packs: bool = False,
) -> str:
    """Apply one reward. Mutates game_state.coins / game_state.bonus_items.
    Pack rewards are opened immediately and their results appended to
    `opened_packs`. If `skip_packs` is True, pack rewards are silently
    skipped (caller has already credited the equivalent cards elsewhere).
    Returns a human-readable line."""
    rtype = reward.reward_type
    amt = reward.amount

    if rtype == "Coins":
        game_state.coins += amt
        return f"+{amt} coins"
    if rtype in _PACK_REWARD_TYPES:
        if skip_packs:
            return f"skipped {amt}x {rtype} (already credited)"
        if config is None or rng is None:
            extras.setdefault("unopened_packs", {})[rtype] = (
                extras.setdefault("unopened_packs", {}).get(rtype, 0) + amt
            )
            return f"+{amt}x {rtype} (queued — no rng/config to open)"
        from simulation.variants.variant_b.day_simulator import open_pack_by_name
        for _ in range(amt):
            result = open_pack_by_name(rtype, game_state, config, rng, apply_evolution=False)
            opened_packs.append(result)
        return f"opened {amt}x {rtype}"
    if rtype in _BONUS_KEY_MAP:
        key = _BONUS_KEY_MAP[rtype]
        game_state.bonus_items[key] = game_state.bonus_items.get(key, 0) + amt
        return f"+{amt} {key}"
    # Unknown type — log to a misc bucket so it isn't silently lost
    misc = extras.setdefault("misc", {})
    misc[rtype] = misc.get(rtype, 0) + amt
    return f"+{amt} {rtype} (misc)"


# ─── Post-pass infinite pack + season cycle ──────────────────────────────────
#
# Once every season-pass step is claimed, the player can claim one "infinite
# pack" per day for the rest of the season. The infinite pack is 2x
# StandardPackT1 (opened immediately, no evolution). Seasons run on a fixed
# cadence (default 28 days); when a season ends the pass resets and must be
# completed again before infinite packs resume.

INFINITE_PACK_TIER = "StandardPackT1"
INFINITE_PACK_COUNT = 2
DEFAULT_SEASON_LENGTH_DAYS = 28


def open_infinite_pack(
    game_state: HeroCardGameState,
    config: HeroCardConfig,
    rng: Random,
    count: int = INFINITE_PACK_COUNT,
    tier: str = INFINITE_PACK_TIER,
) -> List[Dict[str, Any]]:
    """Open the post-pass infinite pack: `count` x `tier` standard packs.

    Packs open immediately via the standard drop flow (no evolution), mirroring
    how season-pass pack rewards are credited. Returns the per-pack result list.
    """
    from simulation.variants.variant_b.day_simulator import open_pack_by_name

    return [
        open_pack_by_name(tier, game_state, config, rng, apply_evolution=False)
        for _ in range(max(0, count))
    ]


def season_index(day: int, season_length: int = DEFAULT_SEASON_LENGTH_DAYS) -> int:
    """0-based season number for a given sim day.

    Day 0 (install/FTUE) and days 1..season_length are season 0; the next
    block of `season_length` days is season 1, and so on.
    """
    if season_length <= 0 or day <= 0:
        return 0
    return (day - 1) // season_length


def day_in_season(day: int, season_length: int = DEFAULT_SEASON_LENGTH_DAYS) -> int:
    """1-based day within the current season (0 on the install day)."""
    if season_length <= 0 or day <= 0:
        return 0
    return (day - 1) % season_length + 1


def days_left_in_season(day: int, season_length: int = DEFAULT_SEASON_LENGTH_DAYS) -> int:
    """Days remaining in the current season, counting the current day as used."""
    if season_length <= 0:
        return 0
    if day <= 0:
        return season_length
    return season_length - day_in_season(day, season_length)


def apply_season_pass_step(
    step_idx_1based: int,
    paid_pass: bool,
    game_state: HeroCardGameState,
    extras: Dict[str, Any],
    config: Optional[HeroCardConfig] = None,
    rng: Optional[Random] = None,
    skip_packs: bool = False,
) -> Tuple[bool, List[str], List[Dict[str, Any]]]:
    """Apply the rewards from one season pass step.

    Args:
        step_idx_1based: 1-based step number (1..len(SEASON_PASS_TABLE)).
        paid_pass: If True, both free and paid rewards apply. Otherwise only free.
        game_state: Mutated for Coins, bonus items, and (for pack rewards) cards.
        extras: Mutated for misc bucket.
        config / rng: Required to open pack rewards immediately. If absent,
            pack rewards fall back to the legacy unopened-pack inventory.
        skip_packs: When True, pack rewards are skipped entirely (used by
            FTUE catch-up where the scripted FTUE already credited the cards
            from the relevant SP packs).

    Returns: (success, log_lines, opened_packs).
        opened_packs is a list of pack-open results (from open_pack_by_name)
        that the UI can render. Empty if no pack rewards were granted.
    """
    if step_idx_1based < 1 or step_idx_1based > len(SEASON_PASS_TABLE):
        return False, [], []

    step = SEASON_PASS_TABLE[step_idx_1based - 1]
    lines: List[str] = []
    opened: List[Dict[str, Any]] = []
    lines.append(f"Step {step.step} (PurpleStar req {step.required_purple_star}):")
    lines.append("  Free:  " + _apply_reward(step.free, game_state, extras, config, rng, opened, skip_packs))
    if paid_pass:
        lines.append("  Paid:  " + _apply_reward(step.paid, game_state, extras, config, rng, opened, skip_packs))
    return True, lines, opened
