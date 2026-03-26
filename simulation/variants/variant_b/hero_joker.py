"""Hero Joker — wildcard duplicate within one hero's deck.

A hero joker can be used as a duplicate for any card in that hero's deck.
The upgrade engine calls consume_joker when a card needs dupes and jokers
are available.
"""

from __future__ import annotations

from simulation.variants.variant_b.models import HeroProgressState


def add_jokers(hero_state: HeroProgressState, count: int) -> None:
    """Add joker cards to a hero's pool."""
    hero_state.joker_count += count


def consume_joker(hero_state: HeroProgressState, count: int = 1) -> int:
    """Consume joker(s) as wildcard duplicates. Returns actual count consumed."""
    available = min(count, hero_state.joker_count)
    hero_state.joker_count -= available
    return available


def jokers_available(hero_state: HeroProgressState) -> int:
    """Return the number of jokers available for this hero."""
    return hero_state.joker_count
