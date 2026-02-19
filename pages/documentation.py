"""
Comprehensive documentation page for the Bluestar Economy Simulator.

Covers all mathematical formulas, system mechanics, data tables, and configuration details.
"""

import streamlit as st


def render_documentation() -> None:
    """Render the complete documentation page."""
    st.title("📖 Bluestar Economy Simulator Documentation")
    st.markdown(
        """
        **Complete technical reference** for all drop algorithms, progression systems, 
        economic models, and configuration tables used in the simulator.
        """
    )

    # Table of Contents
    st.markdown("## Table of Contents")
    st.markdown(
        """
        1. [Overview](#overview)
        2. [Core Systems](#core-systems)
            - [Drop Algorithm](#drop-algorithm)
            - [Progression System](#progression-system)
            - [Upgrade Engine](#upgrade-engine)
            - [Pack System](#pack-system)
            - [Coin Economy](#coin-economy)
        3. [Mathematical Formulas](#mathematical-formulas)
        4. [Data Models](#data-models)
        5. [Configuration Tables](#configuration-tables)
        6. [Simulation Modes](#simulation-modes)
        7. [Implementation Details](#implementation-details)
        """
    )

    st.divider()

    # 1. OVERVIEW
    _render_overview()
    st.divider()

    # 2. CORE SYSTEMS
    _render_core_systems()
    st.divider()

    # 3. MATHEMATICAL FORMULAS
    _render_mathematical_formulas()
    st.divider()

    # 4. DATA MODELS
    _render_data_models()
    st.divider()

    # 5. CONFIGURATION TABLES
    _render_configuration_tables()
    st.divider()

    # 6. SIMULATION MODES
    _render_simulation_modes()
    st.divider()

    # 7. IMPLEMENTATION DETAILS
    _render_implementation_details()


def _render_overview() -> None:
    """Render the overview section."""
    st.markdown("## Overview")
    st.markdown(
        """
        The **Bluestar Economy Simulator** models a dual-resource card collection game 
        with three card categories:
        
        - **Gold Shared Cards**: Primary progression resource (levels 1-100)
        - **Blue Shared Cards**: Secondary progression resource (levels 1-100)
        - **Unique Cards**: Premium cards with gated progression (levels 1-10)
        
        ### Key Concepts
        
        #### Dual-Resource Progression
        Players collect two types of shared cards (Gold and Blue) that progress independently 
        but contribute together to unlock unique card levels. The average shared level acts 
        as a gate for unique progression.
        
        #### Exponential Gap Formula
        The core drop algorithm uses an **exponential gap formula** to balance drops between 
        shared and unique cards based on progression disparity. When unique cards lag behind, 
        their drop weight increases exponentially.
        
        #### Streak System
        Consecutive drops of the same category or card face **multiplicative penalties** to 
        encourage variety and prevent streaks.
        
        #### Economic Balance
        Players earn coins from duplicate cards and spend them (plus bluestars) to upgrade cards. 
        The simulation tracks income/expense flows to validate economic balance.
        """
    )


def _render_core_systems() -> None:
    """Render the core systems section."""
    st.markdown("## Core Systems")

    # Drop Algorithm
    st.markdown("### Drop Algorithm")
    st.markdown(
        """
        The drop algorithm determines which card a player receives from a pack. 
        It operates in **three phases**:
        
        #### Phase 1: Rarity Decision (Shared vs Unique)
        
        Determines whether to drop a Shared or Unique card using the exponential gap formula.
        
        **Implementation:** `simulation/drop_algorithm.py::decide_rarity()`
        
        **Steps:**
        1. **Compute Mapping-Aware Scores** (on [0,1] scale):
           - `gold_prog = compute_mapping_aware_score(cards, GOLD_SHARED, mapping)`
           - `blue_prog = compute_mapping_aware_score(cards, BLUE_SHARED, mapping)`
           - `s_shared = (gold_prog + blue_prog) / 2.0`
           - `s_unique = compute_mapping_aware_score(cards, UNIQUE, mapping)`
        
        2. **Calculate Exponential Gap:**
           - `gap = s_unique - s_shared`
           - `w_shared = BaseShared × gap_base^gap`
           - `w_unique = BaseUnique × gap_base^(-gap)`
           - **Defaults:** `BaseShared=0.70`, `BaseUnique=0.30`, `gap_base=1.5`
        
        3. **Apply Streak Penalties:**
           - `w_shared *= streak_decay_shared^streak_shared`
           - `w_unique *= streak_decay_unique^streak_unique`
           - **Defaults:** `streak_decay_shared=0.6`, `streak_decay_unique=0.3`
        
        4. **Normalize and Roll:**
           - `prob_shared = w_shared / (w_shared + w_unique)`
           - Roll random value to select category
        
        **Special Case:** If all unique cards are maxed, always drop shared.
        
        #### Phase 2: Card Selection (Which Card?)
        
        Selects a specific card from the chosen category using level-based weighting 
        and streak penalties.
        
        **Implementation:** `simulation/drop_algorithm.py::select_card()`
        
        **Steps:**
        1. **Filter Candidates:**
           - If Unique: filter by unlock schedule and gating rules
           - If Shared: filter by color (Gold/Blue)
        
        2. **Compute Card Weights:**
           - `weight_card = 1 / (card.level + 1)`
           - Lower-level cards have higher weight (catch-up mechanic)
        
        3. **Apply Color/Hero Streak Penalties:**
           - `weight_card *= color_decay^streak_color`
           - `weight_card *= hero_decay^streak_hero`
           - **Defaults:** `color_decay=0.6`, `hero_decay=0.3`
        
        4. **Normalize and Roll:**
           - Select card proportional to final weights
        
        #### Phase 3: Duplicate Calculation
        
        Determines how many duplicate copies are received with the card.
        
        **Implementation:** `simulation/drop_algorithm.py::compute_duplicates()`
        
        **Formula:**
        - **Deterministic Mode:** `round(base × (min_pct + max_pct) / 2)`
        - **Monte Carlo Mode:** `round(base × uniform(min_pct, max_pct))`
        
        Where:
        - `base` = base duplicate count from pack config (e.g., 50 for standard pack)
        - `min_pct`, `max_pct` = percentage ranges from `duplicate_ranges` table
        - Ranges vary by card level and category
        
        **Example:**
        - Gold Shared level 1: min=1.0, max=2.0 → 50-100 duplicates (deterministic: 75)
        - Unique level 5: min=0.2, max=0.4 → 10-20 duplicates (deterministic: 15)
        """
    )

    # Progression System
    st.markdown("### Progression System")
    st.markdown(
        """
        The progression system governs how shared and unique cards level up and interact.
        
        **Implementation:** `simulation/progression.py`
        
        #### Progression Mapping
        
        The **progression mapping** defines the relationship between shared and unique card levels. 
        It acts as a gating mechanism: unique cards can only level up if shared cards have 
        progressed sufficiently.
        
        **Structure:** List of `(shared_level, unique_level)` pairs
        
        **Default Mapping:**
        ```
        Shared Level → Max Unique Level
        1  → 1
        5  → 2
        10 → 3
        15 → 4
        20 → 5
        30 → 6
        40 → 7
        50 → 8
        65 → 9
        80 → 10
        ```
        
        #### Mapping-Aware Scoring
        
        **Purpose:** Convert card levels to a normalized [0,1] scale for fair comparison 
        between shared and unique progression.
        
        **Implementation:** `compute_mapping_aware_score(cards, category, mapping)`
        
        **Algorithm:**
        1. **Calculate Average Level:**
           - For shared: `avg_level = sum(card.level for card in category) / count`
           - For unique: same formula
        
        2. **Convert to Shared Scale:**
           - If unique: `equiv_shared = get_equivalent_shared_level(avg_unique, mapping)`
           - If shared: `equiv_shared = avg_level` (already on shared scale)
        
        3. **Normalize to [0,1]:**
           - `score = equiv_shared / max_shared_level`
           - Where `max_shared_level = 100` by default
        
        **Example:**
        - Shared cards at level 40 → score = 40/100 = 0.40
        - Unique cards at level 5 → equiv_shared = 20 (from mapping) → score = 20/100 = 0.20
        - Gap = 0.20 - 0.40 = -0.20 (unique behind) → unique weight increases
        
        #### Gating Logic
        
        **Function:** `get_max_unique_level(avg_shared_level, mapping)`
        
        **Algorithm:**
        - Floor lookup: find highest `shared_level <= avg_shared_level` in mapping
        - Return corresponding `unique_level`
        
        **Example:**
        - If avg_shared = 42 and mapping has entries for 40→7 and 50→8
        - Floor lookup returns 40, so max unique level = 7
        - Unique cards cannot upgrade beyond level 7 until shared reaches 50
        
        #### Unique Unlock Schedule
        
        **Purpose:** Control when unique cards become available for drops.
        
        **Implementation:** `simulation/orchestrator.py::_update_unlock_schedule()`
        
        **Structure:** `{day: [card_id1, card_id2, ...], ...}`
        
        **Default Schedule:**
        ```
        Day 1: First 2 unique cards unlocked
        Day 8: Next 2 unique cards unlocked
        Day 15: Next 2 unique cards unlocked
        Day 22: Next 2 unique cards unlocked
        Day 29: Remaining unique cards unlocked
        ```
        
        **Unlock Logic:**
        - Cards only enter drop pool on/after their unlock day
        - Once unlocked, cards remain available permanently
        - Affects Phase 2 (card selection) filtering
        """
    )

    # Upgrade Engine
    st.markdown("### Upgrade Engine")
    st.markdown(
        """
        The upgrade engine automatically upgrades cards when conditions are met.
        
        **Implementation:** `simulation/upgrade_engine.py::auto_upgrade_all()`
        
        **Strategy:** Greedy algorithm - upgrades all eligible cards each day
        
        #### Upgrade Conditions (ALL must be met)
        
        1. **Sufficient Duplicates:**
           - `card.duplicates >= required_duplicates[card.level - 1]`
           - From `upgrade_tables` config
        
        2. **Sufficient Coins:**
           - `game_state.coins >= required_coins[card.level - 1]`
           - From `upgrade_tables` config
        
        3. **Not At Max Level:**
           - Shared: `card.level < max_shared_level` (default: 100)
           - Unique: `card.level < max_unique_level` (default: 10)
        
        4. **Gating Check (Unique Only):**
           - `card.level < get_max_unique_level(avg_shared_level, mapping)`
           - Ensures unique cards cannot outpace shared progression
        
        #### Upgrade Process
        
        **For each eligible card:**
        1. Deduct duplicates and coins
        2. Increment card level
        3. Award bluestars (from `upgrade_tables`)
        4. Log upgrade event
        
        #### Upgrade Costs
        
        **Tables:** `data/defaults/upgrade_tables.json`
        
        **Structure per category:**
        - `duplicate_costs[i]` = duplicates needed to upgrade from level i to i+1
        - `coin_costs[i]` = coins needed to upgrade from level i to i+1
        - `bluestar_rewards[i]` = bluestars earned when upgrading from level i to i+1
        
        **Example (Gold Shared, levels 1-5):**
        ```
        Level 1→2: 50 dupes, 100 coins → +10 bluestars
        Level 2→3: 75 dupes, 150 coins → +12 bluestars
        Level 3→4: 100 dupes, 200 coins → +15 bluestars
        Level 4→5: 125 dupes, 250 coins → +18 bluestars
        ```
        
        Costs scale progressively with level, with unique cards typically more expensive.
        """
    )

    # Pack System
    st.markdown("### Pack System")
    st.markdown(
        """
        The pack system orchestrates the drop algorithm and processes card packs.
        
        **Implementation:** `simulation/pack_system.py`
        
        #### Pack Structure
        
        Each pack yields multiple card types based on the **card_types_table** configuration.
        
        **Configuration:** `data/defaults/pack_configs.json`
        
        **Structure:**
        ```json
        {
          "name": "Standard Pack",
          "card_types_table": {
            "0": {"min": 3, "max": 3},
            "1": {"min": 2, "max": 2},
            "2": {"min": 1, "max": 1}
          }
        }
        ```
        
        **Interpretation:**
        - Key = unlock threshold (number of unique cards unlocked)
        - Value = range of card types yielded
        - Standard pack: 3 common + 2 uncommon + 1 rare card types
        
        #### Pack Processing Flow
        
        **Function:** `process_pack(game_state, config, pack_config, mode, rng)`
        
        **Steps:**
        1. **Determine Card Types Count:**
           - Lookup current unlock threshold in `card_types_table`
           - **Deterministic:** `(min + max) / 2`
           - **Monte Carlo:** `random.randint(min, max)`
        
        2. **For Each Card Type:**
           - Run drop algorithm (3 phases)
           - Add duplicates to card
           - Update streak states
           - Calculate coin income
        
        3. **Return PackResult:**
           - Total cards pulled
           - Total duplicates received
           - Coins earned from duplicates
        
        #### Daily Pack Schedule
        
        **Configuration:** `data/defaults/daily_pack_schedule.json`
        
        **Structure:** `{day: pack_count, ...}`
        
        **Example:**
        ```json
        {
          "1": 1,
          "2": 1,
          "7": 2,
          "14": 2,
          "30": 3
        }
        ```
        
        **Interpretation:**
        - Days 1-6: 1 pack/day
        - Days 7-13: 2 packs/day
        - Days 14-29: 2 packs/day
        - Day 30+: 3 packs/day
        
        Pack counts scale to reward long-term play and accelerate late-game progression.
        """
    )

    # Coin Economy
    st.markdown("### Coin Economy")
    st.markdown(
        """
        The coin economy tracks income (from duplicates) and expenses (from upgrades).
        
        **Implementation:** `simulation/coin_economy.py`
        
        #### Coin Income
        
        **Function:** `calculate_coin_income(card, duplicates, config, is_deterministic)`
        
        **Formula:**
        - **Non-Maxed Card:** `coins_per_dupe[card.level - 1] × duplicates_received`
        - **Maxed Card:** `coins_per_dupe[0]` (flat rate, level-independent)
        
        **Configuration:** `data/defaults/coin_per_duplicate.json`
        
        **Structure per category:**
        ```json
        {
          "category": "GOLD_SHARED",
          "coins_per_dupe": [10, 12, 14, 16, 18, ...]
        }
        ```
        
        **Example:**
        - Gold Shared level 5 receives 100 duplicates
        - `coins_per_dupe[4] = 18` (0-indexed)
        - Income = 18 × 100 = 1,800 coins
        
        #### Coin Expenses
        
        Coins are spent during upgrades (see Upgrade Engine section).
        
        **Deduction:** `game_state.coins -= upgrade_tables[category].coin_costs[level-1]`
        
        #### Economic Tracking
        
        **CoinLedger Model:**
        - Tracks income and expenses per transaction
        - Validates economic balance over simulation
        - Ensures no negative coin balances (would indicate bug)
        
        **Daily Snapshot:**
        - Records coin balance at end of each day
        - Used for dashboard charts and analysis
        """
    )


def _render_mathematical_formulas() -> None:
    """Render the mathematical formulas section."""
    st.markdown("## Mathematical Formulas")

    st.markdown(
        """
        ### 1. Exponential Gap Formula
        
        **Purpose:** Dynamically weight shared vs unique drop probabilities based on 
        progression disparity.
        
        **Formula:**
        ```
        gap = s_unique - s_shared
        w_shared = BaseShared × gap_base^gap
        w_unique = BaseUnique × gap_base^(-gap)
        prob_shared = w_shared / (w_shared + w_unique)
        ```
        
        **Parameters:**
        - `s_shared`: Normalized shared progression score [0,1]
        - `s_unique`: Normalized unique progression score [0,1]
        - `BaseShared`: Base weight for shared cards (default: 0.70)
        - `BaseUnique`: Base weight for unique cards (default: 0.30)
        - `gap_base`: Exponential scaling factor (default: 1.5)
        
        **Behavior:**
        - When `gap > 0` (unique ahead): shared weight increases, unique weight decreases
        - When `gap < 0` (unique behind): unique weight increases, shared weight decreases
        - When `gap = 0` (balanced): weights equal base values (70/30 split)
        
        **Example:**
        ```
        s_shared = 0.40, s_unique = 0.20
        gap = 0.20 - 0.40 = -0.20
        w_shared = 0.70 × 1.5^(-0.20) = 0.70 × 0.876 = 0.613
        w_unique = 0.30 × 1.5^(0.20) = 0.30 × 1.142 = 0.343
        total = 0.956
        prob_shared = 0.613 / 0.956 = 64.1%
        prob_unique = 0.343 / 0.956 = 35.9%
        ```
        (Unique drops increase from 30% base to 35.9% due to negative gap)
        
        ---
        
        ### 2. Streak Penalty Formula
        
        **Purpose:** Discourage consecutive drops of same category/color/hero.
        
        **Formula:**
        ```
        final_weight = base_weight × decay^streak
        ```
        
        **Parameters:**
        - `base_weight`: Pre-penalty weight from gap formula or card selection
        - `decay`: Decay factor per streak count (0-1 range)
        - `streak`: Number of consecutive drops in category
        
        **Decay Factors (Default):**
        - Shared rarity streak: 0.6
        - Unique rarity streak: 0.3
        - Color streak (Gold/Blue): 0.6
        - Hero streak (specific card): 0.3
        
        **Example:**
        ```
        Initial unique weight = 0.30
        After 3 unique drops in a row:
        final_weight = 0.30 × 0.3^3 = 0.30 × 0.027 = 0.0081
        ```
        (Weight reduced by 97% after 3-streak)
        
        **Streak Reset:**
        - Rarity streaks reset when opposite category drops
        - Color/hero streaks reset when different color/hero drops
        
        ---
        
        ### 3. Card Selection Weight Formula
        
        **Purpose:** Favor lower-level cards to enable catch-up mechanics.
        
        **Formula:**
        ```
        weight_card = 1 / (card.level + 1)
        ```
        
        **After streak penalties:**
        ```
        final_weight = weight_card × color_decay^streak_color × hero_decay^streak_hero
        ```
        
        **Example:**
        ```
        Card A: level 10 → weight = 1/11 = 0.091
        Card B: level 1 → weight = 1/2 = 0.500
        
        Card B is 5.5× more likely to drop (before normalization)
        ```
        
        ---
        
        ### 4. Duplicate Count Formula
        
        **Purpose:** Calculate duplicate copies received with each card drop.
        
        **Deterministic Mode:**
        ```
        duplicates = round(base × (min_pct + max_pct) / 2)
        ```
        
        **Monte Carlo Mode:**
        ```
        duplicates = round(base × uniform(min_pct, max_pct))
        ```
        
        **Parameters:**
        - `base`: Base duplicate count from pack config (e.g., 50)
        - `min_pct`, `max_pct`: Percentage ranges from `duplicate_ranges` table
        - Ranges indexed by `card.level - 1`
        
        **Example:**
        ```
        Base = 50
        Gold Shared level 1: min=1.0, max=2.0
        Deterministic: round(50 × 1.5) = 75 duplicates
        Monte Carlo: round(50 × uniform(1.0, 2.0)) = 50-100 duplicates
        ```
        
        ---
        
        ### 5. Mapping-Aware Score Formula
        
        **Purpose:** Normalize shared and unique progression to [0,1] scale for fair comparison.
        
        **Formula:**
        ```
        avg_level = sum(card.level for card in category) / count
        
        If category == UNIQUE:
            equiv_shared = get_equivalent_shared_level(avg_level, mapping)
        else:
            equiv_shared = avg_level
        
        score = equiv_shared / max_shared_level
        ```
        
        **Equivalent Shared Level (Reverse Lookup):**
        ```
        For each pair (u_lo, s_lo), (u_hi, s_hi) in mapping:
            If u_lo <= avg_unique <= u_hi:
                fraction = (avg_unique - u_lo) / (u_hi - u_lo)
                equiv_shared = s_lo + fraction × (s_hi - s_lo)
        ```
        
        **Example:**
        ```
        Mapping: {1:1, 10:2, 20:3, ...}
        avg_unique = 1.5
        
        Bracketed by (1,1) and (10,2):
        fraction = (1.5 - 1) / (2 - 1) = 0.5
        equiv_shared = 1 + 0.5 × (10 - 1) = 5.5
        score = 5.5 / 100 = 0.055
        ```
        
        ---
        
        ### 6. Coin Income Formula
        
        **Purpose:** Calculate coins earned from duplicate cards.
        
        **Formula:**
        ```
        If card.level < max_level:
            coins = coins_per_dupe[card.level - 1] × duplicates_received
        else:
            coins = coins_per_dupe[0]  (flat rate for maxed cards)
        ```
        
        **Example:**
        ```
        Gold Shared level 5, receives 100 duplicates
        coins_per_dupe[4] = 18
        Income = 18 × 100 = 1,800 coins
        ```
        
        ---
        
        ### 7. Progression Gating Formula
        
        **Purpose:** Limit unique card progression based on shared card progress.
        
        **Formula:**
        ```
        avg_shared = sum(shared_card.level) / count
        max_unique = get_max_unique_level(avg_shared, mapping)
        
        Unique cards can upgrade only if:
            card.level < max_unique
        ```
        
        **Floor Lookup:**
        ```
        max_unique = max(u for (s, u) in mapping if s <= avg_shared)
        ```
        
        **Example:**
        ```
        Mapping: {1:1, 5:2, 10:3, 15:4, 20:5, ...}
        avg_shared = 12
        
        Floor lookup: highest s <= 12 is s=10
        max_unique = 3
        
        Unique cards cannot exceed level 3 until avg_shared reaches 15
        ```
        """
    )


def _render_data_models() -> None:
    """Render the data models section."""
    st.markdown("## Data Models")

    st.markdown(
        """
        All data models use **Pydantic v2** for validation and serialization.
        
        **Implementation:** `simulation/models.py`
        
        ### Core Models
        
        #### Card
        ```python
        class Card(BaseModel):
            id: str                    # Unique identifier
            name: str                  # Display name
            category: CardCategory     # GOLD_SHARED | BLUE_SHARED | UNIQUE
            level: int = 1             # Current level (1-100 shared, 1-10 unique)
            duplicates: int = 0        # Duplicate copies owned
        ```
        
        **Example:**
        ```json
        {
          "id": "gold_001",
          "name": "Warrior",
          "category": "GOLD_SHARED",
          "level": 25,
          "duplicates": 350
        }
        ```
        
        ---
        
        #### CardCategory
        ```python
        class CardCategory(str, Enum):
            GOLD_SHARED = "GOLD_SHARED"
            BLUE_SHARED = "BLUE_SHARED"
            UNIQUE = "UNIQUE"
        ```
        
        **Usage:**
        - Gold/Blue share similar progression (1-100 levels)
        - Unique cards have restricted progression (1-10 levels)
        - Category determines upgrade costs, duplicate ranges, coin rates
        
        ---
        
        #### GameState
        ```python
        class GameState(BaseModel):
            day: int                              # Current simulation day
            cards: List[Card]                     # Player's card collection
            coins: int                            # Current coin balance
            total_bluestars: int                  # Lifetime bluestar earnings
            streak_state: StreakState             # Streak tracking
            unlock_schedule: Dict[str, Any]       # Unique card unlock schedule
            daily_log: List[Any]                  # Event log for analytics
        ```
        
        **Lifecycle:**
        - Initialized at day 0 with starter cards
        - Updated daily by orchestrator
        - Captured in daily snapshots for analysis
        
        ---
        
        #### StreakState
        ```python
        class StreakState(BaseModel):
            streak_shared: int                    # Consecutive shared drops
            streak_unique: int                    # Consecutive unique drops
            streak_per_color: Dict[str, int]      # Streaks by color (gold/blue)
            streak_per_hero: Dict[str, int]       # Streaks by specific card
        ```
        
        **Tracking:**
        - Incremented after each drop
        - Reset when different category/color/hero drops
        - Used to calculate streak penalties in drop algorithm
        
        ---
        
        #### SimConfig
        ```python
        class SimConfig(BaseModel):
            # Initial resources
            initial_coins: int
            initial_bluestars: int
            
            # Card counts
            num_gold_cards: int
            num_blue_cards: int
            num_unique_cards: int
            
            # Level limits
            max_shared_level: int = 100
            max_unique_level: int = 10
            
            # Drop algorithm parameters
            base_shared_rate: float = 0.70
            base_unique_rate: float = 0.30
            gap_base: float = 1.5
            streak_decay_shared: float = 0.6
            streak_decay_unique: float = 0.3
            
            # Configuration tables
            upgrade_tables: List[UpgradeTable]
            duplicate_ranges: List[DuplicateRange]
            coin_per_duplicate: List[CoinPerDuplicate]
            pack_configs: List[PackConfig]
            progression_mapping: ProgressionMapping
            daily_pack_schedule: Dict[int, int]
            unique_unlock_schedule: Dict[int, List[str]]
        ```
        
        **Validation:**
        - All numeric ranges validated at construction
        - Tables validated for completeness (no missing levels)
        - Serializable to/from JSON for URL sharing
        
        ---
        
        #### DailySnapshot
        ```python
        class DailySnapshot(BaseModel):
            day: int
            total_bluestars: int
            coin_balance: int
            avg_gold_level: float
            avg_blue_level: float
            avg_unique_level: float
            upgrades_performed: int
            packs_opened: int
            cards_pulled: int
            unique_cards_unlocked: int
        ```
        
        **Usage:**
        - Captured at end of each simulation day
        - Used to generate time-series charts in dashboard
        - Enables trend analysis and KPI tracking
        
        ---
        
        #### PackResult
        ```python
        class PackResult(BaseModel):
            cards_pulled: int          # Total card types from pack
            duplicates_received: int   # Total duplicate copies
            coins_earned: int          # Coins from duplicates
        ```
        
        **Returned by:** `process_pack()` in `pack_system.py`
        
        ---
        
        #### UpgradeTable
        ```python
        class UpgradeTable(BaseModel):
            category: CardCategory
            duplicate_costs: List[int]     # Indexed by level-1
            coin_costs: List[int]          # Indexed by level-1
            bluestar_rewards: List[int]    # Indexed by level-1
        ```
        
        **Example:**
        ```json
        {
          "category": "GOLD_SHARED",
          "duplicate_costs": [50, 75, 100, 125, ...],
          "coin_costs": [100, 150, 200, 250, ...],
          "bluestar_rewards": [10, 12, 15, 18, ...]
        }
        ```
        
        ---
        
        #### DuplicateRange
        ```python
        class DuplicateRange(BaseModel):
            category: CardCategory
            min_pct: List[float]       # Indexed by level-1
            max_pct: List[float]       # Indexed by level-1
        ```
        
        **Example:**
        ```json
        {
          "category": "GOLD_SHARED",
          "min_pct": [1.0, 0.9, 0.8, 0.7, ...],
          "max_pct": [2.0, 1.8, 1.6, 1.4, ...]
        }
        ```
        
        **Interpretation:**
        - Level 1: 100%-200% of base duplicates
        - Level 2: 90%-180% of base duplicates
        - Higher levels receive proportionally fewer duplicates
        
        ---
        
        #### CoinPerDuplicate
        ```python
        class CoinPerDuplicate(BaseModel):
            category: CardCategory
            coins_per_dupe: List[int]  # Indexed by level-1
        ```
        
        **Example:**
        ```json
        {
          "category": "UNIQUE",
          "coins_per_dupe": [50, 60, 70, 80, 90, 100, ...]
        }
        ```
        
        **Interpretation:**
        - Level 1 unique card: 50 coins per duplicate
        - Level 2 unique card: 60 coins per duplicate
        - Coin value increases with card level
        
        ---
        
        #### ProgressionMapping
        ```python
        class ProgressionMapping(BaseModel):
            shared_levels: List[int]   # Shared level thresholds
            unique_levels: List[int]   # Corresponding unique level gates
        ```
        
        **Example:**
        ```json
        {
          "shared_levels": [1, 5, 10, 15, 20, 30, 40, 50, 65, 80],
          "unique_levels": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        }
        ```
        
        **Interpretation:**
        - When avg_shared < 5: unique cards capped at level 1
        - When avg_shared ≥ 5 and < 10: unique cards capped at level 2
        - When avg_shared ≥ 80: unique cards can reach level 10
        """
    )


def _render_configuration_tables() -> None:
    """Render the configuration tables section."""
    st.markdown("## Configuration Tables")

    st.markdown(
        """
        All configuration tables are stored as JSON files in `data/defaults/`.
        
        ### Table Files
        
        #### 1. upgrade_tables.json
        
        **Purpose:** Define upgrade costs and rewards for each card category.
        
        **Structure:**
        ```json
        [
          {
            "category": "GOLD_SHARED",
            "duplicate_costs": [50, 75, 100, ...],  // 100 entries (levels 1-100)
            "coin_costs": [100, 150, 200, ...],     // 100 entries
            "bluestar_rewards": [10, 12, 15, ...]   // 100 entries
          },
          {
            "category": "BLUE_SHARED",
            "duplicate_costs": [50, 75, 100, ...],
            "coin_costs": [100, 150, 200, ...],
            "bluestar_rewards": [10, 12, 15, ...]
          },
          {
            "category": "UNIQUE",
            "duplicate_costs": [200, 300, 400, ...],  // 10 entries (levels 1-10)
            "coin_costs": [500, 750, 1000, ...],      // 10 entries
            "bluestar_rewards": [50, 60, 70, ...]     // 10 entries
          }
        ]
        ```
        
        **Usage:**
        - Indexed by `card.level - 1` (0-indexed)
        - Upgrade from level N to N+1 uses costs at index N-1
        
        **Example:**
        - Gold Shared card at level 5 wants to upgrade to level 6
        - Required: `duplicate_costs[4] = 125`, `coin_costs[4] = 250`
        - Reward: `bluestar_rewards[4] = 18`
        
        ---
        
        #### 2. duplicate_ranges.json
        
        **Purpose:** Define min/max duplicate percentages per level and category.
        
        **Structure:**
        ```json
        [
          {
            "category": "GOLD_SHARED",
            "min_pct": [1.0, 0.9, 0.8, 0.7, ...],  // 100 entries
            "max_pct": [2.0, 1.8, 1.6, 1.4, ...]   // 100 entries
          },
          {
            "category": "BLUE_SHARED",
            "min_pct": [1.0, 0.9, 0.8, 0.7, ...],
            "max_pct": [2.0, 1.8, 1.6, 1.4, ...]
          },
          {
            "category": "UNIQUE",
            "min_pct": [0.5, 0.45, 0.4, ...],      // 10 entries
            "max_pct": [1.0, 0.9, 0.8, ...]        // 10 entries
          }
        ]
        ```
        
        **Usage:**
        - Indexed by `card.level - 1`
        - Multiplied by pack's base duplicate count
        - Deterministic mode uses average: `(min + max) / 2`
        - Monte Carlo mode samples: `uniform(min, max)`
        
        **Example:**
        - Pack base = 50 duplicates
        - Unique level 3 (index 2): min=0.4, max=0.8
        - Deterministic: `50 × 0.6 = 30` duplicates
        - Monte Carlo: `50 × uniform(0.4, 0.8) = 20-40` duplicates
        
        ---
        
        #### 3. coin_per_duplicate.json
        
        **Purpose:** Define coin rewards per duplicate for each category and level.
        
        **Structure:**
        ```json
        [
          {
            "category": "GOLD_SHARED",
            "coins_per_dupe": [10, 12, 14, 16, 18, ...]  // 100 entries
          },
          {
            "category": "BLUE_SHARED",
            "coins_per_dupe": [10, 12, 14, 16, 18, ...]  // 100 entries
          },
          {
            "category": "UNIQUE",
            "coins_per_dupe": [50, 60, 70, 80, 90, ...]  // 10 entries
          }
        ]
        ```
        
        **Usage:**
        - Non-maxed cards: `coins = coins_per_dupe[level-1] × duplicates`
        - Maxed cards: `coins = coins_per_dupe[0]` (flat rate)
        
        **Design Note:**
        - Higher-level cards earn more coins per duplicate
        - Encourages progression and rewards late-game play
        - Unique cards earn significantly more coins (5x shared rate)
        
        ---
        
        #### 4. pack_configs.json
        
        **Purpose:** Define pack contents and card types yielded at different unlock thresholds.
        
        **Structure:**
        ```json
        [
          {
            "name": "Standard Pack",
            "card_types_table": {
              "0": {"min": 3, "max": 3},
              "2": {"min": 4, "max": 4},
              "4": {"min": 5, "max": 5},
              "6": {"min": 6, "max": 6},
              "8": {"min": 6, "max": 7}
            }
          }
        ]
        ```
        
        **Interpretation:**
        - Key = number of unique cards unlocked
        - Value = range of card types in pack
        - When 0-1 unique unlocked: 3 card types per pack
        - When 2-3 unique unlocked: 4 card types per pack
        - When 8+ unique unlocked: 6-7 card types per pack (MC variance)
        
        **Usage:**
        - Lookup current unlock count in `card_types_table`
        - Use floor lookup (highest key ≤ unlock count)
        - Deterministic: `(min + max) / 2`
        - Monte Carlo: `randint(min, max)`
        
        ---
        
        #### 5. progression_mapping.json
        
        **Purpose:** Define shared-to-unique level gating relationship.
        
        **Structure:**
        ```json
        {
          "shared_levels": [1, 5, 10, 15, 20, 30, 40, 50, 65, 80],
          "unique_levels": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        }
        ```
        
        **Interpretation:**
        - Paired entries: `(shared_levels[i], unique_levels[i])`
        - Defines gates: unique level N requires avg_shared ≥ shared_levels[N-1]
        
        **Example Gates:**
        - Unique level 1: Requires avg_shared ≥ 1 (always available)
        - Unique level 5: Requires avg_shared ≥ 20
        - Unique level 10: Requires avg_shared ≥ 80
        
        **Design Philosophy:**
        - Early unique levels unlock quickly (shared 1-20 → unique 1-5)
        - Late unique levels require heavy shared investment (shared 80 → unique 10)
        - Encourages balanced progression across all card types
        
        ---
        
        #### 6. daily_pack_schedule.json
        
        **Purpose:** Define how many packs players receive each day.
        
        **Structure:**
        ```json
        {
          "1": 1,
          "7": 2,
          "14": 2,
          "30": 3,
          "60": 4
        }
        ```
        
        **Interpretation:**
        - Key = day number (threshold)
        - Value = packs per day from that day forward
        - Uses floor lookup (highest day ≤ current day)
        
        **Example:**
        - Days 1-6: 1 pack/day
        - Days 7-13: 2 packs/day
        - Days 14-29: 2 packs/day
        - Days 30-59: 3 packs/day
        - Day 60+: 4 packs/day
        
        **Design Note:**
        - Accelerates progression for engaged players
        - Rewards long-term retention
        - Balances early-game vs late-game resource flow
        
        ---
        
        #### 7. unique_unlock_schedule.json
        
        **Purpose:** Control when unique cards become available in drop pool.
        
        **Structure:**
        ```json
        {
          "1": ["unique_001", "unique_002"],
          "8": ["unique_003", "unique_004"],
          "15": ["unique_005", "unique_006"],
          "22": ["unique_007", "unique_008"],
          "29": ["unique_009", "unique_010"]
        }
        ```
        
        **Interpretation:**
        - Key = day number
        - Value = list of card IDs unlocked on that day
        - Once unlocked, cards remain available permanently
        
        **Example:**
        - Day 1: 2 unique cards available
        - Day 8: 4 unique cards available (2 new + 2 previous)
        - Day 29: All 10 unique cards available
        
        **Design Philosophy:**
        - Gradual introduction prevents overwhelming new players
        - Creates progression milestones
        - Affects `card_types_table` lookup in pack system
        """
    )


def _render_simulation_modes() -> None:
    """Render the simulation modes section."""
    st.markdown("## Simulation Modes")

    st.markdown(
        """
        The simulator supports two execution modes with different variance characteristics.
        
        ### Deterministic Mode
        
        **Purpose:** Single-run simulation with reproducible results.
        
        **Implementation:** `simulation/orchestrator.py::run_simulation(mode="deterministic")`
        
        **Characteristics:**
        - Fixed random seed for reproducibility
        - All ranges use midpoint: `(min + max) / 2`
        - Same inputs always produce same outputs
        - Fast execution (single pass)
        
        **Use Cases:**
        - Initial configuration testing
        - Debugging specific scenarios
        - Generating baseline expectations
        - Comparing configuration changes
        
        **Output:**
        - Single `SimulationResult` object
        - Daily snapshots showing exact progression
        - Event log with all drops/upgrades
        
        **Example:**
        - Pack yields 3.5 card types → always 3.5 (or rounded)
        - Duplicate range [0.5, 1.0] → always 0.75
        - Same drop sequence every run
        
        ---
        
        ### Monte Carlo Mode
        
        **Purpose:** Multi-run simulation capturing probabilistic variance.
        
        **Implementation:** `simulation/monte_carlo.py::run_monte_carlo()`
        
        **Characteristics:**
        - Runs 1000 independent simulations
        - Each run uses different random seed
        - All ranges sampled uniformly: `uniform(min, max)`
        - Computes mean and variance using Welford algorithm
        
        **Use Cases:**
        - Probability distribution analysis
        - Risk assessment (variance/outliers)
        - Economic balance validation
        - Player experience modeling
        
        **Output:**
        - `MonteCarloResult` with statistics per day:
          - Mean values (average across 1000 runs)
          - Standard deviations (measure of variance)
          - Min/max bounds (outlier detection)
        
        **Example:**
        - Pack yields 3-4 card types → 1000 samples from this range
        - Duplicate range [0.5, 1.0] → 1000 samples uniformly distributed
        - Distribution shows realistic player variance
        
        #### Welford Algorithm
        
        **Purpose:** Compute running mean and variance without storing all samples.
        
        **Formula:**
        ```
        For each new sample x:
            n = n + 1
            delta = x - mean
            mean = mean + delta / n
            delta2 = x - mean
            M2 = M2 + delta × delta2
        
        After all samples:
            variance = M2 / n
            std_dev = sqrt(variance)
        ```
        
        **Benefits:**
        - Memory-efficient (O(1) space)
        - Numerically stable
        - Real-time updates during simulation
        
        ---
        
        ### Mode Comparison
        
        | Aspect | Deterministic | Monte Carlo |
        |--------|---------------|-------------|
        | Runs | 1 | 1000 |
        | Randomness | Fixed seed | 1000 seeds |
        | Range sampling | Midpoint | Uniform |
        | Output | Single result | Mean + variance |
        | Speed | Fast (~1s) | Moderate (~30s) |
        | Use case | Testing | Analysis |
        
        **Recommendation:**
        - Use **Deterministic** for rapid iteration and config tuning
        - Use **Monte Carlo** for final validation and player experience assessment
        """
    )


def _render_implementation_details() -> None:
    """Render the implementation details section."""
    st.markdown("## Implementation Details")

    st.markdown(
        """
        ### File Structure
        
        ```
        coin_sim/
        ├── simulation/
        │   ├── models.py                 # Pydantic data models
        │   ├── config_loader.py          # Load JSON config tables
        │   ├── drop_algorithm.py         # 3-phase drop algorithm
        │   ├── progression.py            # Mapping-aware scoring, gating
        │   ├── upgrade_engine.py         # Auto-upgrade logic
        │   ├── pack_system.py            # Pack processing
        │   ├── coin_economy.py           # Coin income/expense tracking
        │   ├── orchestrator.py           # Main simulation loop
        │   └── monte_carlo.py            # MC runner with Welford stats
        ├── data/
        │   └── defaults/
        │       ├── upgrade_tables.json
        │       ├── duplicate_ranges.json
        │       ├── coin_per_duplicate.json
        │       ├── pack_configs.json
        │       ├── progression_mapping.json
        │       ├── daily_pack_schedule.json
        │       └── unique_unlock_schedule.json
        ├── pages/
        │   ├── config_editor.py          # Config UI
        │   ├── simulation_controls.py    # Run simulation UI
        │   ├── dashboard.py              # Charts and analytics
        │   ├── pull_log_viewer.py        # Event log viewer
        │   └── documentation.py          # This file
        ├── app.py                        # Streamlit entry point
        └── tests/                        # 176 unit/integration tests
        ```
        
        ---
        
        ### Orchestrator Flow
        
        **Function:** `simulation/orchestrator.py::run_simulation()`
        
        **Pseudocode:**
        ```python
        def run_simulation(config, num_days, mode):
            # Initialize game state
            game_state = initialize_game_state(config)
            daily_snapshots = []
            
            for day in range(1, num_days + 1):
                game_state.day = day
                
                # 1. Update unlock schedule
                unlock_new_unique_cards(game_state, config)
                
                # 2. Process daily packs
                pack_count = get_pack_count_for_day(day, config)
                for _ in range(pack_count):
                    pack_result = process_pack(game_state, config, mode)
                    game_state.coins += pack_result.coins_earned
                    update_card_duplicates(game_state, pack_result)
                
                # 3. Auto-upgrade eligible cards
                upgrade_result = auto_upgrade_all(game_state, config)
                game_state.coins -= upgrade_result.coins_spent
                game_state.total_bluestars += upgrade_result.bluestars_earned
                
                # 4. Capture daily snapshot
                snapshot = create_snapshot(game_state)
                daily_snapshots.append(snapshot)
            
            return SimulationResult(daily_snapshots, game_state.daily_log)
        ```
        
        **Key Points:**
        - Order matters: unlocks → packs → upgrades → snapshot
        - Upgrades happen immediately after packs (greedy strategy)
        - Snapshots capture end-of-day state for analytics
        
        ---
        
        ### Drop Algorithm Flow
        
        **Function:** `simulation/pack_system.py::process_pack()`
        
        **Pseudocode:**
        ```python
        def process_pack(game_state, config, mode, rng):
            # Determine card types count
            unlocked_count = count_unlocked_unique_cards(game_state)
            card_types = lookup_card_types(unlocked_count, config, mode, rng)
            
            pack_result = PackResult()
            
            for _ in range(card_types):
                # Phase 1: Decide rarity (shared vs unique)
                category = decide_rarity(game_state, config, streak_state, rng)
                update_rarity_streak(streak_state, category)
                
                # Phase 2: Select specific card
                card = select_card(game_state, category, config, streak_state, rng)
                update_card_streak(streak_state, card)
                
                # Phase 3: Compute duplicates
                duplicates = compute_duplicates(card, config, mode, rng)
                card.duplicates += duplicates
                
                # Calculate coin income
                coins = calculate_coin_income(card, duplicates, config, mode)
                pack_result.coins_earned += coins
                pack_result.duplicates_received += duplicates
                pack_result.cards_pulled += 1
            
            return pack_result
        ```
        
        **Key Points:**
        - Each card type goes through all 3 phases
        - Streaks updated after each card (affects next card in pack)
        - Coins calculated immediately based on card level
        
        ---
        
        ### Upgrade Logic Flow
        
        **Function:** `simulation/upgrade_engine.py::auto_upgrade_all()`
        
        **Pseudocode:**
        ```python
        def auto_upgrade_all(game_state, config):
            upgrade_result = UpgradeResult()
            
            # Sort cards by priority (optional: Gold > Blue > Unique)
            cards = sorted(game_state.cards, key=lambda c: c.category)
            
            for card in cards:
                while can_upgrade(card, game_state, config):
                    # Deduct costs
                    required_dupes = get_duplicate_cost(card, config)
                    required_coins = get_coin_cost(card, config)
                    card.duplicates -= required_dupes
                    game_state.coins -= required_coins
                    
                    # Perform upgrade
                    card.level += 1
                    
                    # Award bluestars
                    bluestars = get_bluestar_reward(card, config)
                    upgrade_result.bluestars_earned += bluestars
                    upgrade_result.upgrades_performed += 1
                    upgrade_result.coins_spent += required_coins
                    
                    # Log event
                    game_state.daily_log.append(upgrade_event)
            
            return upgrade_result
        ```
        
        **Key Points:**
        - Greedy strategy: upgrade all eligible cards immediately
        - `while` loop handles multiple levels per card per day
        - Unique cards check gating constraint on each iteration
        
        ---
        
        ### Configuration Loading
        
        **Function:** `simulation/config_loader.py::load_defaults()`
        
        **Process:**
        1. Read all JSON files from `data/defaults/`
        2. Parse into Pydantic models
        3. Validate completeness (all levels covered)
        4. Return `SimConfig` object
        
        **Error Handling:**
        - Missing files → raise FileNotFoundError
        - Invalid JSON → raise ValueError with line number
        - Incomplete tables → raise ValidationError with details
        
        **URL Sharing:**
        - `encode_config()`: SimConfig → JSON → gzip → base64url
        - `decode_config()`: base64url → gzip → JSON → SimConfig
        - Compression reduces 50KB config to ~2-3KB URL
        
        ---
        
        ### Testing Strategy
        
        **Test Suite:** `tests/` (176 tests)
        
        **Coverage:**
        - Unit tests for each formula (gap, streak, duplicates, coins)
        - Integration tests for multi-day simulations
        - Regression tests for known edge cases
        - Property tests for invariants (e.g., coins never negative)
        
        **Key Test Cases:**
        - Gap formula symmetry: `gap(A, B) = -gap(B, A)`
        - Streak decay monotonicity: longer streaks → lower weights
        - Gating enforcement: unique level never exceeds gate
        - Economic balance: total_income ≈ total_expenses (within tolerance)
        - Deterministic reproducibility: same seed → same result
        
        **Run Tests:**
        ```bash
        pytest tests/ -v
        ```
        
        ---
        
        ### Performance Considerations
        
        **Deterministic Mode:**
        - 100-day simulation: ~1 second
        - Bottleneck: card selection weight calculation
        - Optimization: cache mapping-aware scores
        
        **Monte Carlo Mode:**
        - 1000 runs × 100 days: ~30 seconds
        - Bottleneck: repeated drop algorithm calls
        - Optimization: parallel processing (not yet implemented)
        - Memory: O(days) space (Welford algorithm)
        
        **UI Responsiveness:**
        - Long simulations run in background
        - Progress bar updates every 100 runs
        - Results cached in session state
        
        ---
        
        ### Future Enhancements
        
        **Potential Features:**
        1. **Custom Pack Types**: Multiple pack configs with different card counts
        2. **Dynamic Scheduling**: Packs based on player actions, not just day
        3. **Parallel Monte Carlo**: Use multiprocessing for faster MC runs
        4. **Advanced Upgrade Strategies**: Priority-based, resource-constrained
        5. **Event System**: Special events that modify drop rates temporarily
        6. **Player Profiles**: Multiple progression curves for different player types
        
        **Configuration Extensions:**
        - Non-linear duplicate ranges (exponential decay)
        - Dynamic gap_base based on progression phase
        - Soft gating (penalties instead of hard blocks)
        - Card synergies (bonuses for balanced collections)
        """
    )

    st.divider()
    st.markdown(
        """
        ## End of Documentation
        
        For questions or suggestions, please refer to the codebase or contact the development team.
        
        **Last Updated:** February 2026  
        **Version:** 1.0.0  
        **Codebase:** `/Users/mertt7/Documents/GitHub/coin_sim`
        """
    )
