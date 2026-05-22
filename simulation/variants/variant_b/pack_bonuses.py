"""Pack bonus items + per-pack duplicate boost (Variant B).

Every regular pack opening (StandardPackT1-T5, EndOfChapterPack, HeroPack,
PetPack, GearPack) carries a number of *bonus item slots*. Each slot
independently rolls each bonus item type at the per-pack probability,
and rolled items grant `base_amount * uniform(bottom%, top%)` rounded.

Some packs also boost the duplicate count of dropped cards by a per-pack
shared/unique multiplier (e.g. T4 gives +25% shared dupes / +10% unique
dupes on every card dropped from a T4 pack).

All tables are hardcoded per the design spec.
"""

from __future__ import annotations

from random import Random
from typing import Dict, Optional, Tuple

# Canonical bonus item keys (also used as keys in game_state.bonus_items)
HERO_TOKENS    = "HeroTokens"
PET_FOOD       = "PetFood"
SPIRIT_STONE   = "SpiritStone"
PET_EGG        = "PetEgg"
RANDOM_DESIGN  = "RandomDesign"
RANDOM_GEAR    = "RandomGear"
S_STONE        = "S-Stone"
EVERSTONE      = "Everstone"
DIAMONDS       = "Diamonds"
PURPLE_STARS   = "PurpleStars"  # Not in pack bonus tables — used elsewhere

BONUS_ITEM_KEYS = [
    HERO_TOKENS, PET_FOOD, SPIRIT_STONE, PET_EGG,
    RANDOM_DESIGN, RANDOM_GEAR, S_STONE, EVERSTONE, DIAMONDS, PURPLE_STARS,
]


# Number of independent bonus-item slots per pack open.
PACK_BONUS_SLOTS: Dict[str, int] = {
    "StandardPackT1":   1,
    "StandardPackT2":   1,
    "StandardPackT3":   2,
    "StandardPackT4":   3,
    "StandardPackT5":   6,
    "EndOfChapterPack": 3,
    "HeroPack":         3,
    "PetPack":          5,
    "GearPack":         4,
}


# Per-slot Bernoulli probability that each item drops (independent rolls).
PACK_BONUS_PROBS: Dict[str, Dict[str, float]] = {
    "StandardPackT1": {
        HERO_TOKENS: 0.00, PET_FOOD: 0.00, SPIRIT_STONE: 0.00, PET_EGG: 0.00,
        RANDOM_DESIGN: 0.00, RANDOM_GEAR: 0.00, S_STONE: 0.00, EVERSTONE: 0.00, DIAMONDS: 0.00,
    },
    "StandardPackT2": {
        HERO_TOKENS: 0.00, PET_FOOD: 0.30, SPIRIT_STONE: 0.20, PET_EGG: 0.20,
        RANDOM_DESIGN: 0.30, RANDOM_GEAR: 0.40, S_STONE: 0.00, EVERSTONE: 0.00, DIAMONDS: 0.00,
    },
    "StandardPackT3": {
        HERO_TOKENS: 0.10, PET_FOOD: 0.50, SPIRIT_STONE: 0.30, PET_EGG: 0.30,
        RANDOM_DESIGN: 0.40, RANDOM_GEAR: 0.50, S_STONE: 0.00, EVERSTONE: 0.00, DIAMONDS: 0.15,
    },
    "StandardPackT4": {
        HERO_TOKENS: 0.20, PET_FOOD: 1.00, SPIRIT_STONE: 0.50, PET_EGG: 0.30,
        RANDOM_DESIGN: 0.50, RANDOM_GEAR: 0.50, S_STONE: 0.01, EVERSTONE: 0.05, DIAMONDS: 0.25,
    },
    "StandardPackT5": {
        HERO_TOKENS: 0.50, PET_FOOD: 1.00, SPIRIT_STONE: 1.00, PET_EGG: 1.00,
        RANDOM_DESIGN: 1.00, RANDOM_GEAR: 0.10, S_STONE: 0.50, EVERSTONE: 0.10, DIAMONDS: 0.50,
    },
    "EndOfChapterPack": {
        HERO_TOKENS: 0.50, PET_FOOD: 0.50, SPIRIT_STONE: 0.50, PET_EGG: 0.50,
        RANDOM_DESIGN: 0.50, RANDOM_GEAR: 0.50, S_STONE: 0.00, EVERSTONE: 0.00, DIAMONDS: 0.10,
    },
    "HeroPack": {
        HERO_TOKENS: 1.00, PET_FOOD: 0.00, SPIRIT_STONE: 0.00, PET_EGG: 0.00,
        RANDOM_DESIGN: 0.00, RANDOM_GEAR: 0.00, S_STONE: 0.00, EVERSTONE: 0.00, DIAMONDS: 0.10,
    },
    "PetPack": {
        HERO_TOKENS: 0.00, PET_FOOD: 1.00, SPIRIT_STONE: 1.00, PET_EGG: 1.00,
        RANDOM_DESIGN: 0.00, RANDOM_GEAR: 0.00, S_STONE: 0.00, EVERSTONE: 0.02, DIAMONDS: 0.10,
    },
    "GearPack": {
        HERO_TOKENS: 0.00, PET_FOOD: 0.00, SPIRIT_STONE: 0.00, PET_EGG: 0.00,
        RANDOM_DESIGN: 1.00, RANDOM_GEAR: 1.00, S_STONE: 0.02, EVERSTONE: 0.00, DIAMONDS: 0.10,
    },
}


# Per-pack, per-item base amount granted when the roll lands.
PACK_BONUS_AMOUNTS: Dict[str, Dict[str, int]] = {
    "StandardPackT1": {
        HERO_TOKENS: 0, PET_FOOD: 0, SPIRIT_STONE: 0, PET_EGG: 0,
        RANDOM_DESIGN: 0, RANDOM_GEAR: 0, S_STONE: 0, EVERSTONE: 0, DIAMONDS: 0,
    },
    "StandardPackT2": {
        HERO_TOKENS: 0, PET_FOOD: 20, SPIRIT_STONE: 50, PET_EGG: 5,
        RANDOM_DESIGN: 10, RANDOM_GEAR: 1, S_STONE: 0, EVERSTONE: 0, DIAMONDS: 0,
    },
    "StandardPackT3": {
        HERO_TOKENS: 30, PET_FOOD: 20, SPIRIT_STONE: 100, PET_EGG: 15,
        RANDOM_DESIGN: 15, RANDOM_GEAR: 1, S_STONE: 0, EVERSTONE: 0, DIAMONDS: 25,
    },
    "StandardPackT4": {
        HERO_TOKENS: 50, PET_FOOD: 50, SPIRIT_STONE: 125, PET_EGG: 20,
        RANDOM_DESIGN: 20, RANDOM_GEAR: 1, S_STONE: 1, EVERSTONE: 1, DIAMONDS: 30,
    },
    "StandardPackT5": {
        HERO_TOKENS: 150, PET_FOOD: 200, SPIRIT_STONE: 500, PET_EGG: 50,
        RANDOM_DESIGN: 50, RANDOM_GEAR: 2, S_STONE: 1, EVERSTONE: 2, DIAMONDS: 50,
    },
    "EndOfChapterPack": {
        HERO_TOKENS: 50, PET_FOOD: 200, SPIRIT_STONE: 80, PET_EGG: 15,
        RANDOM_DESIGN: 15, RANDOM_GEAR: 1, S_STONE: 0, EVERSTONE: 0, DIAMONDS: 25,
    },
    "HeroPack": {
        HERO_TOKENS: 40, PET_FOOD: 0, SPIRIT_STONE: 0, PET_EGG: 0,
        RANDOM_DESIGN: 0, RANDOM_GEAR: 0, S_STONE: 0, EVERSTONE: 0, DIAMONDS: 25,
    },
    "PetPack": {
        HERO_TOKENS: 0, PET_FOOD: 150, SPIRIT_STONE: 120, PET_EGG: 25,
        RANDOM_DESIGN: 0, RANDOM_GEAR: 0, S_STONE: 0, EVERSTONE: 2, DIAMONDS: 25,
    },
    "GearPack": {
        HERO_TOKENS: 0, PET_FOOD: 0, SPIRIT_STONE: 0, PET_EGG: 0,
        RANDOM_DESIGN: 25, RANDOM_GEAR: 2, S_STONE: 1, EVERSTONE: 0, DIAMONDS: 25,
    },
}


# Per-pack (bottom, top) multiplier applied to base amount on each drop.
PACK_BONUS_VARIANCE: Dict[str, Tuple[float, float]] = {
    "StandardPackT1":   (0.70, 1.10),
    "StandardPackT2":   (0.70, 1.20),
    "StandardPackT3":   (0.70, 1.20),
    "StandardPackT4":   (0.70, 1.20),
    "StandardPackT5":   (0.70, 1.60),
    "EndOfChapterPack": (0.70, 1.20),
    "HeroPack":         (0.70, 1.20),
    "PetPack":          (0.70, 1.20),
    "GearPack":         (0.70, 1.20),
}


# Per-pack (shared_card_boost, unique_card_boost) applied to dupes received.
# Final dupes = round(base_dupes * (1 + boost)).
PACK_DUPE_BOOST: Dict[str, Tuple[float, float]] = {
    "StandardPackT1":   (0.00, 0.00),
    "StandardPackT2":   (0.00, 0.00),
    "StandardPackT3":   (0.05, 0.03),
    "StandardPackT4":   (0.25, 0.10),
    "StandardPackT5":   (0.50, 0.50),
    "EndOfChapterPack": (0.00, 0.00),
    "HeroPack":         (0.00, 0.00),
    "PetPack":          (0.00, 0.00),
    "GearPack":         (0.00, 0.00),
}


def roll_pack_bonuses(pack_name: str, rng: Optional[Random]) -> Dict[str, int]:
    """Roll all bonus item slots for a pack opening.

    Returns a dict mapping item_name -> total amount granted (or empty if no rolls
    landed). Each of the pack's slots independently rolls each item type at the
    per-pack probability and credits round(base_amount * uniform(bottom, top))
    when the roll lands.
    """
    if pack_name not in PACK_BONUS_SLOTS:
        return {}
    slots = PACK_BONUS_SLOTS[pack_name]
    probs = PACK_BONUS_PROBS.get(pack_name, {})
    amounts = PACK_BONUS_AMOUNTS.get(pack_name, {})
    bottom, top = PACK_BONUS_VARIANCE.get(pack_name, (1.0, 1.0))

    result: Dict[str, int] = {}
    if rng is None:
        return result  # No bonuses in deterministic mode

    for _ in range(slots):
        for item, prob in probs.items():
            if prob <= 0:
                continue
            if rng.random() < prob:
                base = amounts.get(item, 0)
                if base <= 0:
                    continue
                mult = rng.uniform(bottom, top)
                granted = max(1, round(base * mult))
                result[item] = result.get(item, 0) + granted
    return result


def get_dupe_boost(pack_name: str) -> Tuple[float, float]:
    """Return (shared_card_boost, unique_card_boost) for a pack name."""
    return PACK_DUPE_BOOST.get(pack_name, (0.0, 0.0))
