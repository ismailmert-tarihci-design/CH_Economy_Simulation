"""
Pack processing system for the Bluestar Economy Simulator.

Handles pack opening mechanics:
- Deterministic vs Monte Carlo pack count selection
- Card types table lookups with floor matching
- CardPull tracking for daily simulation
"""

from dataclasses import dataclass
from random import Random
from typing import Optional

import numpy as np

from simulation.models import GameState, SimConfig


@dataclass
class CardPull:
    """Represents a single card pull from a pack."""

    pack_name: str
    pull_index: int


def _get_card_types_for_count(
    card_types_table: dict[int, int], total_unlocked: int
) -> int:
    """
    Look up card types for a given total unlocked count using floor matching.

    Args:
        card_types_table: Dict mapping threshold → card_types count
        total_unlocked: Total number of unlocked cards

    Returns:
        Card types count for the highest threshold ≤ total_unlocked

    Raises:
        ValueError: If total_unlocked is less than minimum table key
    """
    matching_keys = [k for k in card_types_table.keys() if k <= total_unlocked]
    if not matching_keys:
        raise ValueError(
            f"total_unlocked ({total_unlocked}) is below minimum table key "
            f"({min(card_types_table.keys())})"
        )

    best_key = max(matching_keys)
    return card_types_table[best_key]


def process_packs_for_day(
    game_state: GameState,
    config: SimConfig,
    rng: Optional[Random] = None,
) -> list[CardPull]:
    """
    Process pack openings for a single day.

    For each pack type in config:
    - Compute number of packs to open (deterministic or MC)
    - Look up card types for current total_unlocked
    - Generate CardPull objects for each card

    Args:
        game_state: Current game state (contains current card collection)
        config: Simulation configuration with pack_averages and pack definitions
        rng: Random instance for MC mode (None = deterministic)

    Returns:
        List of CardPull objects for the day
    """
    pulls: list[CardPull] = []
    total_unlocked = len(game_state.cards)

    for pack_config in config.packs:
        pack_name = pack_config.name

        # Get average packs for this type
        daily_avg = config.pack_averages.get(pack_name, 0.0)

        # Determine number of packs to open
        if rng is None:
            # Deterministic: round to nearest integer
            num_packs = round(daily_avg)
        else:
            # MC: Use Poisson distribution
            num_packs = int(np.random.poisson(daily_avg))

        # Generate pulls for each pack
        for pack_index in range(num_packs):
            # Look up card types for current unlocked count
            card_types = _get_card_types_for_count(
                pack_config.card_types_table,
                total_unlocked,
            )

            # Create CardPull for each card type
            for card_index in range(card_types):
                pull = CardPull(
                    pack_name=pack_name,
                    pull_index=len(pulls),
                )
                pulls.append(pull)

    return pulls
