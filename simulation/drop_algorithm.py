"""
Phase 1 of Card Drop Algorithm: Rarity Decision (Shared vs Unique).

Implements the 5-step weighted algorithm with progression gap balancing
and streak penalties as specified in the Revamp Master Doc.
"""

from random import Random
from typing import Optional

from simulation.models import CardCategory, GameState, SimConfig, StreakState
from simulation.progression import compute_category_progression

# Constants for streak decay rates
STREAK_DECAY_SHARED = 0.6
STREAK_DECAY_UNIQUE = 0.3
GAP_BASE = 1.5


def decide_rarity(
    game_state: GameState,
    config: SimConfig,
    streak_state: StreakState,
    rng: Optional[Random] = None,
) -> CardCategory:
    """
    Phase 1: Decide whether to drop a Shared or Unique card.

    Implements 5-step algorithm:
    1. Compute progression scores (SShared, SUnique)
    2. Apply gap adjustment (exponential balancing)
    3. Apply streak penalties (exponential decay)
    4. Normalize probabilities
    5. Roll weighted random (or deterministic if rng=None)

    Args:
        game_state: Current game state with card collection
        config: Simulation configuration with base rates and progression mapping
        streak_state: Current streak state for penalty calculation
        rng: Random number generator for Monte Carlo mode (None = deterministic)

    Returns:
        CardCategory.GOLD_SHARED or CardCategory.UNIQUE
        (Phase 2 will handle Gold vs Blue selection)

    Algorithm Reference:
        Revamp Master Doc - RARITY DECISION flowchart
    """
    # Step 1: Compute Progression Scores
    # SShared = average of Gold + Blue progression
    gold_prog = compute_category_progression(
        game_state.cards, CardCategory.GOLD_SHARED, config.progression_mapping
    )
    blue_prog = compute_category_progression(
        game_state.cards, CardCategory.BLUE_SHARED, config.progression_mapping
    )
    s_shared = (gold_prog + blue_prog) / 2.0

    # SUnique = average of all Unique cards
    s_unique = compute_category_progression(
        game_state.cards, CardCategory.UNIQUE, config.progression_mapping
    )

    # Step 2: Gap Adjustment
    # Gap = SUnique - SShared
    # WShared = base_shared_rate * (GAP_BASE ^ Gap)
    # WUnique = base_unique_rate * (GAP_BASE ^ -Gap)
    gap = s_unique - s_shared
    w_shared = config.base_shared_rate * (GAP_BASE**gap)
    w_unique = config.base_unique_rate * (GAP_BASE ** (-gap))

    # Step 3: Streak Penalty
    # FinalShared = WShared * (STREAK_DECAY_SHARED ^ streak_shared)
    # FinalUnique = WUnique * (STREAK_DECAY_UNIQUE ^ streak_unique)
    final_shared = w_shared * (STREAK_DECAY_SHARED**streak_state.streak_shared)
    final_unique = w_unique * (STREAK_DECAY_UNIQUE**streak_state.streak_unique)

    # Step 4: Normalize
    total = final_shared + final_unique
    prob_shared = final_shared / total
    # prob_unique = final_unique / total  # Not needed for roll

    # Step 5: Roll
    if rng is None:
        # Deterministic mode: choose majority category
        return CardCategory.GOLD_SHARED if prob_shared >= 0.5 else CardCategory.UNIQUE
    else:
        # Monte Carlo mode: weighted random roll
        return (
            CardCategory.GOLD_SHARED
            if rng.random() < prob_shared
            else CardCategory.UNIQUE
        )


def update_rarity_streak(
    streak_state: StreakState, chosen: CardCategory
) -> StreakState:
    """
    Update rarity streaks based on chosen category.

    When a Shared card is chosen (GOLD_SHARED or BLUE_SHARED):
    - Increment streak_shared
    - Reset streak_unique to 0

    When a Unique card is chosen:
    - Increment streak_unique
    - Reset streak_shared to 0

    Args:
        streak_state: Current streak state
        chosen: The CardCategory that was chosen by decide_rarity()

    Returns:
        New StreakState with updated rarity streaks
        (color and hero streaks are preserved, updated in Phase 2)
    """
    new_state = StreakState(
        streak_shared=streak_state.streak_shared,
        streak_unique=streak_state.streak_unique,
        streak_per_color=streak_state.streak_per_color.copy(),
        streak_per_hero=streak_state.streak_per_hero.copy(),
    )

    if chosen in (CardCategory.GOLD_SHARED, CardCategory.BLUE_SHARED):
        # Shared card chosen
        new_state.streak_shared += 1
        new_state.streak_unique = 0
    else:  # CardCategory.UNIQUE
        # Unique card chosen
        new_state.streak_unique += 1
        new_state.streak_shared = 0

    return new_state
