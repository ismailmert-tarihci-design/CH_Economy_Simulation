"""FTUE — First-Time User Experience — for Variant B day simulator.

Scripted, deterministic onboarding sequence that runs on Day 0 (install day).
After the FTUE finishes, the player holds the dupes/bluestars/XP/tokens
dictated by the spec: 260 cumulative bluestars, 365 Woodie XP, 250 hero
tokens, and 10 diamonds. It walks through End-of-Chapter 3/4/5 packs
explicitly (chapters 1–2 completed off-screen), leaving chapters_beaten = 5.

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


FTUE_END_CHAPTER = 5


# ---------------------------------------------------------------------------
# Card name -> Woody card_id mapping
# ---------------------------------------------------------------------------
#
# Woody pool (standardized 13G/10B/2Gr): woody_gold_1..13, woody_blue_1..10,
# woody_gray_1..2. Gray has only 2 slots so multiple FTUE gray names share IDs.

FTUE_CARD_MAP: Dict[str, str] = {
    # Gold-rarity tagged in spec
    "Power Shot":       "woody_gold_1",
    "Hawk Shot":        "woody_gold_2",
    "Bounce Shot":      "woody_gold_3",
    "Vital Surge ++":   "woody_gold_4",
    "Extra Shot":       "woody_gold_5",
    "Ball Fortune":     "woody_gold_6",
    "Double Strike":    "woody_gold_7",
    # Blue-rarity tagged in spec
    "Bronze Shield":    "woody_blue_1",
    "Steel Hide":       "woody_blue_2",
    "Vicious Impact":   "woody_blue_3",
    "Battle Cry":       "woody_blue_4",
    "Sharp Instinct":   "woody_blue_5",
    "Sharp Instinct +": "woody_blue_5",  # perked variant maps to same card
    "Shadow Step":      "woody_blue_6",
    "Fury":             "woody_blue_7",
    "Healing Spell+":   "woody_blue_8",
    # Gray-rarity tagged in spec — only 2 gray slots, so reuse heavily
    "Life Drain":       "woody_gray_1",
    "Ball Stash":       "woody_gray_2",
    "Simple Shots":     "woody_gray_1",
    "Simple Shots+":    "woody_gray_1",
    "Healing Spell":    "woody_gray_2",
    "Vital Surge":      "woody_gray_1",
    "Wooden Shield":    "woody_gray_2",
    "Crit power":       "woody_gray_2",
}


@dataclass
class FtueStep:
    """One scripted pack-and-upgrade event in the FTUE."""
    label: str
    card_drops: List[Tuple[str, int]] = field(default_factory=list)   # [(name, dupes)]
    upgrades: List[Tuple[str, int]] = field(default_factory=list)     # [(name, bluestars_reward)]
    coins: int = 0
    diamonds: int = 0
    hero_tokens: int = 0
    xp_gain: int = 0


# ---------------------------------------------------------------------------
# Scripted FTUE sequence (deterministic, exactly as design spec)
# ---------------------------------------------------------------------------

FTUE_STEPS: List[FtueStep] = [
    FtueStep(
        label="1st Training Pack (→ T2)",
        card_drops=[("Power Shot", 29), ("Bronze Shield", 35)],
    ),
    FtueStep(
        label="2nd Training Pack (→ T4)",
        card_drops=[("Power Shot", 34), ("Life Drain", 20), ("Ball Stash", 23), ("Simple Shots", 8)],
        upgrades=[("Power Shot", 30)],
        xp_gain=50,
    ),
    FtueStep(
        label="End of Chapter 3 Pack",
        card_drops=[("Bounce Shot", 28), ("Life Drain", 33)],
        upgrades=[("Life Drain", 10)],
        xp_gain=25,
    ),
    FtueStep(
        label="3rd Training Pack (→ T3)",
        card_drops=[("Vital Surge ++", 35), ("Bronze Shield", 19), ("Steel Hide", 23)],
        upgrades=[("Bronze Shield", 10)],
        xp_gain=25,
    ),
    FtueStep(
        label="BlueStar Milestone L2 Pack",
        card_drops=[("Vital Surge ++", 37), ("Vicious Impact", 24)],
        upgrades=[("Vital Surge ++", 30)],
        xp_gain=50,
    ),
    FtueStep(
        label="End of Chapter 4 Pack",
        card_drops=[("Hawk Shot", 34), ("Ball Fortune", 27)],
    ),
    FtueStep(
        label="SeasonPass Step 1 Pack (→ T2)",
        card_drops=[("Steel Hide", 29), ("Healing Spell", 12), ("Power Shot", 25)],
        upgrades=[("Steel Hide", 10)],
        xp_gain=25,
    ),
    FtueStep(
        label="1st Daily Pack (→ T2)",
        card_drops=[("Extra Shot", 32), ("Healing Spell", 10)],
        upgrades=[("Healing Spell", 10)],
        xp_gain=10,
    ),
    FtueStep(
        label="2nd Daily Pack (→ T1)",
        card_drops=[("Hawk Shot", 29), ("Battle Cry", 23)],
        upgrades=[("Hawk Shot", 30)],
        xp_gain=50,
    ),
    FtueStep(
        label="SeasonPass Step 2 Pack (→ T2)",
        card_drops=[("Vicious Impact", 27), ("Sharp Instinct", 13)],
        upgrades=[("Vicious Impact", 10)],
        xp_gain=25,
    ),
    FtueStep(
        label="3rd Daily Pack (→ T4)",
        card_drops=[
            ("Extra Shot", 37), ("Battle Cry", 28), ("Ball Fortune", 25), ("Simple Shots+", 9),
        ],
        upgrades=[("Extra Shot", 30), ("Battle Cry", 10), ("Ball Fortune", 10)],
        diamonds=10,
        xp_gain=50,
    ),
    FtueStep(
        label="BlueStar Milestone L3 Pack",
        card_drops=[("Bounce Shot", 34), ("Simple Shots", 13)],
        upgrades=[("Bounce Shot", 30), ("Simple Shots", 10)],
        hero_tokens=250,
        xp_gain=25,
    ),
    FtueStep(
        label="End of Chapter 5 Pack",
        card_drops=[("Power Shot", 30), ("Wooden Shield", 12)],
    ),
    FtueStep(
        label="4th Daily Pack (→ T2)",
        card_drops=[("Power Shot", 42), ("Sharp Instinct +", 27)],
        upgrades=[("Power Shot", 30)],
        xp_gain=30,
    ),
    FtueStep(
        label="SeasonPass Step 4 Pack (→ T3)",
        card_drops=[("Double Strike", 27), ("Shadow Step", 31), ("Vital Surge", 11)],
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

    upgrade_tables = {t.rarity.value: t for t in config.hero_upgrade_tables}

    def _next_cost(card) -> int:
        """Dupe cost for the card's next level-up, or 0 if maxed/unknown."""
        table = upgrade_tables.get(card.rarity.value)
        if not table or card.level - 1 >= len(table.duplicate_costs):
            return 0
        return table.duplicate_costs[card.level - 1]

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
            # Spend the real dupe cost for this level-up (clamped at 0 so a
            # short FTUE grant can't go negative), then level up + award BS.
            dupe_cost = _next_cost(card)
            card.duplicates = max(0, card.duplicates - dupe_cost)
            card.level += 1
            game_state.total_bluestars += bs_reward
            log.append(f"  upgrade {name} L{old_level}→L{card.level} (-{dupe_cost} dupes, +{bs_reward} bluestars)")

        # Coins / diamonds
        if step.coins:
            game_state.coins += step.coins
            log.append(f"  +{step.coins} coins")
        if step.diamonds:
            game_state.bonus_items["Diamonds"] = game_state.bonus_items.get("Diamonds", 0) + step.diamonds
            log.append(f"  +{step.diamonds} diamonds")
        if step.hero_tokens:
            game_state.bonus_items["HeroTokens"] = game_state.bonus_items.get("HeroTokens", 0) + step.hero_tokens
            log.append(f"  +{step.hero_tokens} hero tokens")

        # XP + level-ups
        if step.xp_gain:
            woody.xp += step.xp_gain
            leveled = _check_hero_level_up(woody, hero_def)
            tail = f" → Woody L{woody.level}" if leveled else ""
            log.append(f"  +{step.xp_gain} XP{tail}")

    # Cap leftover duplicates below each card's next-level cost. The FTUE's
    # card-name → id reuse (esp. the 2 gray slots) can still pile dupes past a
    # threshold; this enforces the post-greedy-play invariant so nothing is
    # instantly upgradeable when the FTUE ends.
    for card in woody.cards.values():
        if not card.unlocked:
            continue
        next_cost = _next_cost(card)
        if next_cost and card.duplicates >= next_cost:
            card.duplicates = next_cost - 1

    game_state.chapters_beaten = FTUE_END_CHAPTER
    log.append(f"  chapters beaten set to {FTUE_END_CHAPTER} (post-FTUE state)")

    log.append(
        f"── FTUE complete: Woody L{woody.level} (XP {woody.xp}), "
        f"coins {game_state.coins:,}, bluestars {game_state.total_bluestars}, "
        f"chapters {game_state.chapters_beaten} ──"
    )
    return log
