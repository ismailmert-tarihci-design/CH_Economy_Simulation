"""
Phase 1 of Card Drop Algorithm: Rarity Decision (Shared vs Unique).

Implements the 5-step weighted algorithm with progression gap balancing
and streak penalties as specified in the Revamp Master Doc.
"""

from random import Random
from typing import Optional

from simulation.models import Card, CardCategory, GameState, SimConfig, StreakState
from simulation.progression import compute_category_progression

# Legacy constants kept for backward compatibility (tests, external imports).
# The simulation reads these values from SimConfig fields instead.
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
    # WShared = base_shared_rate * (gap_base ^ Gap)
    # WUnique = base_unique_rate * (gap_base ^ -Gap)
    gap = s_unique - s_shared
    w_shared = config.base_shared_rate * (config.gap_base**gap)
    w_unique = config.base_unique_rate * (config.gap_base ** (-gap))

    # Step 3: Streak Penalty
    # FinalShared = WShared * (streak_decay_shared ^ streak_shared)
    # FinalUnique = WUnique * (streak_decay_unique ^ streak_unique)
    final_shared = w_shared * (config.streak_decay_shared**streak_state.streak_shared)
    final_unique = w_unique * (config.streak_decay_unique**streak_state.streak_unique)

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


def select_shared_card(
    game_state: GameState,
    config: SimConfig,
    streak_state: StreakState,
    rng: Optional[Random] = None,
) -> Card:
    """
    Phase 2a: Select a shared card from Gold + Blue pools using weighted selection.

    Algorithm (from Revamp Master Doc):
    1. Get ALL shared cards (Gold + Blue) sorted by level ascending
    2. Take top N lowest level (N = all shared, since 23 < 33 threshold)
    3. For each candidate:
       - WeightCard = 1 / (card.level + 1)
       - streak_for_color = streak_state.streak_per_color.get(card.category.value, 0)
       - FinalWeight = WeightCard * (0.6 ** streak_for_color)
    4. Selection:
       - Deterministic: pick card with highest FinalWeight
       - MC: weighted random choice

    Args:
        game_state: Current game state with card collection
        config: Simulation configuration
        streak_state: Current streak state for penalty calculation
        rng: Random number generator for Monte Carlo mode (None = deterministic)

    Returns:
        Selected shared card (Gold or Blue)

    Algorithm Reference:
        Revamp Master Doc - SHARED CARD SELECTION flowchart
    """
    # Get all shared cards
    shared_cards = [
        c
        for c in game_state.cards
        if c.category in (CardCategory.GOLD_SHARED, CardCategory.BLUE_SHARED)
    ]

    # Sort by level ascending
    shared_cards.sort(key=lambda c: c.level)

    # Compute weights for each candidate
    weights = []
    for card in shared_cards:
        base_weight = 1.0 / (card.level + 1)

        # Get color streak (use category.value as key: "GOLD_SHARED" or "BLUE_SHARED")
        color_streak = streak_state.streak_per_color.get(card.category.value, 0)

        final_weight = base_weight * (config.streak_decay_shared**color_streak)
        weights.append(final_weight)

    # Selection
    if rng is None:
        # Deterministic: pick highest weighted
        max_idx = weights.index(max(weights))
        return shared_cards[max_idx]
    else:
        # MC: weighted random choice
        return rng.choices(shared_cards, weights=weights, k=1)[0]


def select_unique_card(
    game_state: GameState,
    config: SimConfig,
    streak_state: StreakState,
    rng: Optional[Random] = None,
) -> Card:
    """
    Phase 2b: Select a unique card using weighted selection.

    Algorithm (from Revamp Master Doc):
    1. Get all UNLOCKED unique cards sorted by level ascending
    2. Take top N lowest level (N = config.unique_candidate_pool)
    3. For each candidate:
       - WeightCard = 1 / (card.level + 1)
       - streak_for_hero = streak_state.streak_per_hero.get(card.id, 0)
       - FinalWeight = WeightCard * (streak_decay_shared ** streak_for_hero)
    4. Selection:
       - Deterministic: pick card with highest FinalWeight
       - MC: weighted random choice

    Args:
        game_state: Current game state with card collection
        config: Simulation configuration
        streak_state: Current streak state for penalty calculation
        rng: Random number generator for Monte Carlo mode (None = deterministic)

    Returns:
        Selected unique card

    Algorithm Reference:
        Revamp Master Doc - UNIQUE CARD SELECTION flowchart
    """
    # Get all unique cards
    unique_cards = [c for c in game_state.cards if c.category == CardCategory.UNIQUE]

    # Sort by level ascending
    unique_cards.sort(key=lambda c: c.level)

    # Take top N (or all if fewer)
    candidates = unique_cards[: config.unique_candidate_pool]

    # Compute weights
    weights = []
    for card in candidates:
        base_weight = 1.0 / (card.level + 1)

        # Get hero streak (use card.id as key)
        hero_streak = streak_state.streak_per_hero.get(card.id, 0)

        final_weight = base_weight * (config.streak_decay_shared**hero_streak)
        weights.append(final_weight)

    # Selection
    if rng is None:
        max_idx = weights.index(max(weights))
        return candidates[max_idx]
    else:
        return rng.choices(candidates, weights=weights, k=1)[0]


def update_card_streak(
    game_state: GameState, streak_state: StreakState, selected_card: Card
) -> StreakState:
    """
    Update color/hero streaks after card selection.

    For Shared cards:
    - Increment streak for selected color (GOLD or BLUE)
    - Reset other color streak to 0

    For Unique cards:
    - Increment streak for selected hero (by card.id)
    - Reset all other hero streaks to 0

    Args:
        game_state: Current game state (needed to iterate all unique cards)
        streak_state: Current streak state
        selected_card: The card that was selected

    Returns:
        New StreakState with updated color/hero streaks
    """
    new_state = StreakState(
        streak_shared=streak_state.streak_shared,
        streak_unique=streak_state.streak_unique,
        streak_per_color=streak_state.streak_per_color.copy(),
        streak_per_hero=streak_state.streak_per_hero.copy(),
    )

    if selected_card.category == CardCategory.GOLD_SHARED:
        new_state.streak_per_color["GOLD_SHARED"] = (
            streak_state.streak_per_color.get("GOLD_SHARED", 0) + 1
        )
        new_state.streak_per_color["BLUE_SHARED"] = 0
    elif selected_card.category == CardCategory.BLUE_SHARED:
        new_state.streak_per_color["BLUE_SHARED"] = (
            streak_state.streak_per_color.get("BLUE_SHARED", 0) + 1
        )
        new_state.streak_per_color["GOLD_SHARED"] = 0
    else:  # UNIQUE
        # Increment selected hero
        new_state.streak_per_hero[selected_card.id] = (
            streak_state.streak_per_hero.get(selected_card.id, 0) + 1
        )

        # Reset all other heroes
        for card in game_state.cards:
            if card.category == CardCategory.UNIQUE and card.id != selected_card.id:
                new_state.streak_per_hero[card.id] = 0

    return new_state


def compute_duplicates_received(
    card: Card, config: SimConfig, rng: Optional[Random] = None
) -> int:
    """
    Calculate duplicates received for selected card.

    Algorithm:
    1. Check if card is MAXED → return 0
    2. Get base = upgrade_tables[category].duplicate_costs[level - 1]
    3. Get min_pct, max_pct from duplicate_ranges[category][level - 1]
    4. Deterministic: round(base * (min_pct + max_pct) / 2)
       MC: round(base * rng.uniform(min_pct, max_pct))

    Args:
        card: The card receiving duplicates
        config: Simulation configuration
        rng: Random number generator for Monte Carlo mode (None = deterministic)

    Returns:
        Number of duplicate copies received
    """
    # Check if maxed
    max_level = (
        config.max_unique_level
        if card.category == CardCategory.UNIQUE
        else config.max_shared_level
    )
    if card.level >= max_level:
        return 0

    # Get base from upgrade costs
    upgrade_table = config.upgrade_tables[card.category]
    base = upgrade_table.duplicate_costs[card.level - 1]

    # Get percentile range
    dup_range = config.duplicate_ranges[card.category]
    min_pct = dup_range.min_pct[card.level - 1]
    max_pct = dup_range.max_pct[card.level - 1]

    # Calculate
    if rng is None:
        # Deterministic: midpoint
        return round(base * (min_pct + max_pct) / 2.0)
    else:
        # MC: random within range
        return round(base * rng.uniform(min_pct, max_pct))


def perform_card_pull(
    game_state: GameState,
    config: SimConfig,
    streak_state: StreakState,
    rng: Optional[Random] = None,
) -> tuple[Card, int, int, StreakState]:
    """
    Full card pull orchestration.

    Flow:
    1. Phase 1: Decide rarity (shared vs unique)
    2. Update rarity streak
    3. Phase 2: Select specific card
    4. Update card streak (color/hero)
    5. Compute duplicates received
    6. Compute coin income
    7. Return (card, duplicates, coins, updated_streak_state)

    Args:
        game_state: Current game state with card collection
        config: Simulation configuration
        streak_state: Current streak state
        rng: Random number generator for Monte Carlo mode (None = deterministic)

    Returns:
        Tuple of (selected_card, duplicates_received, coins_earned, updated_streak_state)
    """
    from simulation.coin_economy import compute_coin_income

    chosen_category = decide_rarity(game_state, config, streak_state, rng)
    streak_state = update_rarity_streak(streak_state, chosen_category)

    if chosen_category in (CardCategory.GOLD_SHARED, CardCategory.BLUE_SHARED):
        selected_card = select_shared_card(game_state, config, streak_state, rng)
    else:
        selected_card = select_unique_card(game_state, config, streak_state, rng)

    streak_state = update_card_streak(game_state, streak_state, selected_card)
    duplicates = compute_duplicates_received(selected_card, config, rng)
    coins = compute_coin_income(selected_card, duplicates, config)

    return (selected_card, duplicates, coins, streak_state)
