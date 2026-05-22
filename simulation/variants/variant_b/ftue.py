"""FTUE — First-Time User Experience — for Variant B day simulator.

Scripted, deterministic onboarding sequence that runs on Day 0 (install day).
After the FTUE finishes, the player is at Woodie Level 4 with 305 cumulative
XP, holding the dupes/coins/bluestars/etc. dictated by the FTUE spec.

Mechanics:
  - Card drops: credit fixed dupe counts to specific cards (unlocking them).
  - Forced upgrades: bypass cost (dupes/coins not consumed), grant explicit
    bluestar reward, and add the step's XP to the hero. Per design intent
    (`override every first upgrade for woodie unique cards`), XP is taken
    from the step total, not from the hero_upgrade_table.
  - Coins / diamonds: credit directly.

The card-name → card_id mapping is intentionally loose ("not super important"
per design) — FTUE card names like "Power Shot" map to woody_card_20, etc.,
re-using card_ids when the FTUE references more uniques than Woodie's pool has.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from simulation.variants.variant_b.models import HeroCardConfig, HeroCardGameState
from simulation.variants.variant_b.upgrade_engine import _check_hero_level_up


# ---------------------------------------------------------------------------
# Card name -> Woody card_id mapping
# ---------------------------------------------------------------------------
#
# Woody has 12 GRAY (woody_card_1..12), 7 BLUE (..13..19), 5 GOLD (..20..24).
# FTUE references more golds than that, so some FTUE names share a card_id.

FTUE_CARD_MAP: Dict[str, str] = {
    # Gold-rarity tagged in spec
    "Power Shot":       "woody_card_20",
    "Hawk Shot":        "woody_card_21",
    "Bounce Shot":      "woody_card_22",
    "Vital Surge ++":   "woody_card_23",
    "Extra Shot":       "woody_card_24",
    "Ball Fortune":     "woody_card_20",  # reuse
    "Double Strike":    "woody_card_21",  # reuse
    # Blue-rarity tagged in spec
    "Bronze Shield":    "woody_card_13",
    "Steel Hide":       "woody_card_14",
    "Vicious Impact":   "woody_card_15",
    "Battle Cry":       "woody_card_16",
    "Sharp Instinct":   "woody_card_17",
    "Sharp Instinct +": "woody_card_17",  # perked variant maps to same card
    "Shadow Step":      "woody_card_18",
    "Fury":             "woody_card_19",
    "Healing Spell+":   "woody_card_19",  # reuse
    # Gray-rarity tagged in spec
    "Life Drain":       "woody_card_1",
    "Ball Stash":       "woody_card_2",
    "Simple Shots":     "woody_card_3",
    "Simple Shots+":    "woody_card_3",
    "Healing Spell":    "woody_card_4",
    "Vital Surge":      "woody_card_5",
    "Crit power":       "woody_card_6",
}


@dataclass
class FtueStep:
    """One scripted pack-and-upgrade event in the FTUE."""
    label: str
    card_drops: List[Tuple[str, int]] = field(default_factory=list)   # [(name, dupes)]
    upgrades: List[Tuple[str, int]] = field(default_factory=list)     # [(name, bluestars_reward)]
    coins: int = 0
    diamonds: int = 0
    xp_gain: int = 0


# ---------------------------------------------------------------------------
# Scripted FTUE sequence (deterministic, exactly as design spec)
# ---------------------------------------------------------------------------

FTUE_STEPS: List[FtueStep] = [
    FtueStep(
        label="1st Training Pack (→ T2)",
        card_drops=[("Power Shot", 29), ("Bronze Shield", 35)],
        coins=60,
    ),
    FtueStep(
        label="2nd Training Pack (→ T4)",
        card_drops=[("Power Shot", 34), ("Life Drain", 20), ("Ball Stash", 23), ("Simple Shots", 8)],
        upgrades=[("Power Shot", 30)],
        coins=205,
        xp_gain=30,
    ),
    FtueStep(
        label="End of Chapter 3 Pack",
        card_drops=[("Bounce Shot", 28), ("Life Drain", 33)],
        upgrades=[("Life Drain", 10)],
        coins=75,
        xp_gain=25,
    ),
    FtueStep(
        label="3rd Training Pack (→ T3)",
        card_drops=[("Vital Surge ++", 35), ("Bronze Shield", 19), ("Steel Hide", 23)],
        upgrades=[("Bronze Shield", 10)],
        coins=125,
        xp_gain=25,
    ),
    FtueStep(
        label="BlueStar Milestone L2 Pack",
        card_drops=[("Vital Surge ++", 37), ("Vicious Impact", 24)],
        upgrades=[("Vital Surge ++", 30)],
        coins=80,
        xp_gain=30,
    ),
    FtueStep(
        label="End of Chapter 4 Pack",
        card_drops=[("Hawk Shot", 34), ("Ball Fortune", 27)],
        coins=70,
    ),
    FtueStep(
        label="SeasonPass Step 1 Pack (→ T2)",
        card_drops=[("Steel Hide", 29), ("Healing Spell", 12), ("Power Shot", 25)],
        upgrades=[("Steel Hide", 10)],
        coins=85,
        xp_gain=25,
    ),
    FtueStep(
        label="1st Daily Pack (→ T2)",
        card_drops=[("Extra Shot", 32), ("Healing Spell", 10)],
        upgrades=[("Healing Spell", 10)],
        coins=165,
        xp_gain=10,
    ),
    FtueStep(
        label="2nd Daily Pack (→ T1)",
        card_drops=[("Hawk Shot", 29), ("Battle Cry", 23)],
        upgrades=[("Hawk Shot", 30)],
        coins=60,
        xp_gain=30,
    ),
    FtueStep(
        label="SeasonPass Step 2 Pack (→ T2)",
        card_drops=[("Vicious Impact", 27), ("Sharp Instinct", 13)],
        upgrades=[("Vicious Impact", 10)],
        coins=80,
        xp_gain=25,
    ),
    FtueStep(
        label="3rd Daily Pack (→ T4)",
        card_drops=[
            ("Extra Shot", 37), ("Battle Cry", 28), ("Ball Fortune", 25), ("Simple Shots+", 9),
        ],
        upgrades=[("Extra Shot", 50), ("Battle Cry", 10), ("Ball Fortune", 10)],
        coins=350,
        diamonds=10,
        xp_gain=50,
    ),
    FtueStep(
        label="End of Chapter 5 Pack",
        card_drops=[("Power Shot", 30), ("Healing Spell+", 23)],
        coins=90,
    ),
    FtueStep(
        label="4th Daily Pack (→ T2)",
        card_drops=[("Bounce Shot", 34), ("Sharp Instinct +", 27)],
        upgrades=[("Bounce Shot", 30)],
        coins=70,
    ),
    FtueStep(
        label="BlueStar Milestone L3 Pack",
        card_drops=[("Power Shot", 42), ("Healing Spell+", 29)],
        upgrades=[("Power Shot", 30), ("Healing Spell+", 10), ("Fury", 40)],
        coins=80,
        xp_gain=55,
    ),
    FtueStep(
        label="SeasonPass Step 4 Pack (→ T3)",
        card_drops=[("Double Strike", 27), ("Shadow Step", 31), ("Vital Surge", 11)],
        coins=125,
    ),
]


def run_ftue(
    game_state: HeroCardGameState,
    config: HeroCardConfig,
    extras: Dict[str, Any],
) -> List[str]:
    """Auto-play the FTUE on D0. Mutates game_state + extras. Returns log lines."""
    log: List[str] = ["── FTUE start (D0, install day) ──"]
    if "woody" not in game_state.heroes:
        return log + ["[FTUE skipped: Woody not in game state]"]

    woody = game_state.heroes["woody"]
    hero_def = next((h for h in config.heroes if h.hero_id == "woody"), None)
    if hero_def is None:
        return log + ["[FTUE skipped: no Woody hero_def in config]"]

    for step in FTUE_STEPS:
        log.append(f"FTUE | {step.label}")

        # Card drops (unlock if needed, then credit dupes)
        for name, dupes in step.card_drops:
            card_id = FTUE_CARD_MAP.get(name)
            if not card_id or card_id not in woody.cards:
                log.append(f"  ! unmapped FTUE card: {name}")
                continue
            card = woody.cards[card_id]
            newly_unlocked = not card.unlocked
            card.unlocked = True
            card.duplicates += dupes
            unlock_note = " (unlock)" if newly_unlocked else ""
            log.append(f"  +{dupes} dupes → {name} [{card_id}]{unlock_note}")

        # Forced upgrades (bypass cost, explicit BS reward; XP credited via step.xp_gain)
        for name, bs_reward in step.upgrades:
            card_id = FTUE_CARD_MAP.get(name)
            if not card_id or card_id not in woody.cards:
                log.append(f"  ! unmapped FTUE upgrade target: {name}")
                continue
            card = woody.cards[card_id]
            card.unlocked = True
            old_level = card.level
            card.level += 1
            game_state.total_bluestars += bs_reward
            log.append(f"  upgrade {name} L{old_level}→L{card.level} (+{bs_reward} bluestars, free)")

        # Coins / diamonds
        if step.coins:
            game_state.coins += step.coins
            log.append(f"  +{step.coins} coins")
        if step.diamonds:
            extras["diamonds"] = extras.get("diamonds", 0) + step.diamonds
            log.append(f"  +{step.diamonds} diamonds")

        # XP + level-ups
        if step.xp_gain:
            woody.xp += step.xp_gain
            leveled = _check_hero_level_up(woody, hero_def)
            tail = f" → Woody L{woody.level}" if leveled else ""
            log.append(f"  +{step.xp_gain} XP{tail}")

    log.append(
        f"── FTUE complete: Woody L{woody.level} (XP {woody.xp}), "
        f"coins {game_state.coins:,}, bluestars {game_state.total_bluestars} ──"
    )
    return log
