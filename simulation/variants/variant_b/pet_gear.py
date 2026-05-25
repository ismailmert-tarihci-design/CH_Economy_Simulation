"""Per-hero pet & gear progression (Variant B).

Each hero owns its own pet and gear, advanced by opening PetPacks / GearPacks
against that hero. Variant B's pet/gear is intentionally simpler than
Variant A's table-driven system:

  * Pet: a single per-hero "pet" with a level (1..PET_MAX_LEVEL). Each PetPack
    opened against the hero credits PET_XP_PER_PACK; level-ups happen when XP
    crosses PET_XP_PER_LEVEL.

  * Gear: a small fixed set of slots per hero (HERO_GEAR_SLOTS). Each GearPack
    opened against the hero upgrades one slot by one level, round-robin across
    the slots.

The "target hero" for a PetPack/GearPack is the most-recently-unlocked hero
(`game_state.last_unlocked_hero`). This matches Variant B's design intent
that new heroes are the focus of progression. If no hero has been explicitly
marked, the helper falls back to the most-recent entry in `game_state.heroes`
(insertion-ordered).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from simulation.variants.variant_b.models import (
    HERO_GEAR_SLOTS,
    HeroCardGameState,
    HeroGearState,
    HeroPetState,
    HeroProgressState,
)


# Pet progression knobs. Hardcoded — Variant B's pet/gear is a coarse
# secondary system; tunables can be lifted to config later if needed.
PET_MAX_LEVEL: int = 30
PET_XP_PER_PACK: int = 50
PET_XP_PER_LEVEL: int = 100

# Gear progression knobs. Each GearPack bumps one slot by one level (round
# robin). Slot cap keeps gear comparable to pet.
GEAR_MAX_LEVEL: int = 30


@dataclass
class PetUpgradeEvent:
    hero_id: str
    pet_levels_gained: int
    new_level: int
    xp_after: int


@dataclass
class GearUpgradeEvent:
    hero_id: str
    slot: str
    old_level: int
    new_level: int


def pick_pack_target(game_state: HeroCardGameState) -> Optional[str]:
    """Pick the hero to receive a PetPack / GearPack upgrade.

    Routing rule: most-recently-unlocked hero
    (`game_state.last_unlocked_hero`), falling back to the last entry in
    `game_state.heroes` if that hint is unset (covers day-0 starter heroes
    that were inserted before the orchestrator started tracking unlocks).
    Returns None when no heroes are unlocked yet.
    """
    if not game_state.heroes:
        return None
    target = game_state.last_unlocked_hero
    if target and target in game_state.heroes:
        return target
    # Fallback: pick the last hero inserted into the dict. dict preserves
    # insertion order in Py 3.7+.
    return next(reversed(game_state.heroes))


def apply_pet_pack(
    hero_state: HeroProgressState,
    xp_gained: int = PET_XP_PER_PACK,
) -> PetUpgradeEvent:
    """Apply one PetPack opening to a hero. Returns the resulting event."""
    pet: HeroPetState = hero_state.pet
    pet.pet_packs_opened += 1
    old_level = pet.level
    if pet.level >= PET_MAX_LEVEL:
        # Already capped — XP still accumulates but doesn't raise level.
        pet.xp += xp_gained
        return PetUpgradeEvent(
            hero_id=hero_state.hero_id,
            pet_levels_gained=0,
            new_level=pet.level,
            xp_after=pet.xp,
        )
    pet.xp += xp_gained
    while pet.xp >= PET_XP_PER_LEVEL and pet.level < PET_MAX_LEVEL:
        pet.xp -= PET_XP_PER_LEVEL
        pet.level += 1
    return PetUpgradeEvent(
        hero_id=hero_state.hero_id,
        pet_levels_gained=pet.level - old_level,
        new_level=pet.level,
        xp_after=pet.xp,
    )


def apply_gear_pack(hero_state: HeroProgressState) -> Optional[GearUpgradeEvent]:
    """Apply one GearPack opening to a hero. Returns the resulting event.

    Round-robin across HERO_GEAR_SLOTS. Returns None if every slot is at the
    cap (so callers can log "no-op").
    """
    gear: HeroGearState = hero_state.gear
    gear.gear_packs_opened += 1
    if not HERO_GEAR_SLOTS:
        return None
    # Try up to N slots to find one that's not capped — keeps round-robin
    # progress smooth even when some slots cap before others.
    n = len(HERO_GEAR_SLOTS)
    for offset in range(n):
        idx = (gear.next_slot_index + offset) % n
        slot = HERO_GEAR_SLOTS[idx]
        current = gear.slot_levels.get(slot, 1)
        if current < GEAR_MAX_LEVEL:
            new_level = current + 1
            gear.slot_levels[slot] = new_level
            gear.next_slot_index = (idx + 1) % n
            return GearUpgradeEvent(
                hero_id=hero_state.hero_id,
                slot=slot,
                old_level=current,
                new_level=new_level,
            )
    return None


def gear_total_level(gear: HeroGearState) -> int:
    """Sum of all slot levels for a hero's gear (used by MC aggregation)."""
    return sum(gear.slot_levels.values())
