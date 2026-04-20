"""
Pull-by-pull logging for the Bluestar Economy Simulator.

Captures every card pull event with the selected card, duplicates received,
coins earned, and any upgrades that fired immediately after the pull.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class VariantBUpgradeEvent:
    """Adapter for Variant B upgrade dicts — matches UpgradeEvent interface."""

    card_id: str
    old_level: int
    new_level: int
    dupes_spent: int
    coins_spent: int
    bluestars_earned: int
    day: int
    hero_id: str = ""
    jokers_spent: int = 0
    xp_earned: int = 0


@dataclass
class PullEvent:
    """A single card pull with its immediate consequences."""

    day: int
    pull_index: int  # 1-indexed within the day
    card_id: str
    card_name: str
    card_category: str  # e.g. "GOLD_SHARED", "BLUE_SHARED", "UNIQUE", "HERO_warrior"
    card_level_before: int  # level at the moment of pull
    duplicates_received: int
    duplicates_total_after: int  # total dupes on card after this pull
    coins_earned: int
    pack_name: str  # which pack this pull came from
    bluestars_earned: int  # total bluestars from upgrades after this pull
    upgrades: list[Any] = field(default_factory=list)


@dataclass
class PullLogger:
    """Collects PullEvent records across the entire simulation."""

    events: list[PullEvent] = field(default_factory=list)

    def log_pull(
        self,
        *,
        day: int,
        pull_index: int,
        card_id: str,
        card_name: str,
        card_category: str,
        card_level_before: int,
        duplicates_received: int,
        duplicates_total_after: int,
        coins_earned: int,
        pack_name: str,
        bluestars_earned: int,
        upgrades: list[Any],
    ) -> None:
        self.events.append(
            PullEvent(
                day=day,
                pull_index=pull_index,
                card_id=card_id,
                card_name=card_name,
                card_category=card_category,
                card_level_before=card_level_before,
                duplicates_received=duplicates_received,
                duplicates_total_after=duplicates_total_after,
                coins_earned=coins_earned,
                pack_name=pack_name,
                bluestars_earned=bluestars_earned,
                upgrades=upgrades,
            )
        )
