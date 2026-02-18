# Bluestar Economy Simulator - Learnings

## Task 1: Project Scaffolding (Completed)

### Successful Patterns
- **Directory Structure**: Created modular structure (simulation/, data/defaults/, tests/, pages/, .streamlit/) for clean separation of concerns
- **Streamlit Config**: Set headless=true in config.toml enables deployment-ready configuration
- **Requirements.txt**: Pinned specific versions (e.g., streamlit==1.41.1) for reproducible builds
- **Python .gitignore**: Comprehensive Python standard patterns prevent common issues (__pycache__, .venv, *.pyc, etc.)
- **README.md**: Clear setup instructions with pip install and streamlit run commands

### Conventions Established
- Using Streamlit `set_page_config()` with emoji icon (🌌) for project branding
- config.toml theme uses standard Streamlit colors (primaryColor: #1f77b4)
- App entry point via `app.py` at root level
- Core logic will live in `simulation/` module
- Multi-page content structure ready in `pages/` directory

### Technical Decisions
- **Pydantic**: Included for data validation in simulation models
- **Pytest**: Selected for unit testing framework
- **Plotly**: Preferred over matplotlib for interactive visualizations
- **Streamlit on port 8501**: Standard default, configured explicitly for clarity

### Build Verification
✅ All directories created successfully
✅ All required files in place (requirements.txt, config.toml, app.py, README.md, .gitignore)
✅ Git repository initialized
✅ App launches and serves HTTP 200
✅ Streamlit headless mode verified working

### Next Steps Preparation
- Foundation ready for simulation model implementation
- Pages directory prepared for multi-page app expansion
- Tests directory ready for test suite development

## Task 5: Progression & Gating Logic (Completed)

### Implementation Patterns

#### 1. Floor Lookup for Gating
- **Pattern**: Find highest `shared_level ≤ avg_shared_level` and return corresponding unique level
- **Key Code**:
  ```python
  for shared_level in mapping.shared_levels:
      if shared_level <= avg_shared_level:
          applicable_level = shared_level
      else:
          break
  idx = mapping.shared_levels.index(applicable_level)
  return mapping.unique_levels[idx]
  ```
- **Why this works**: Sorted mapping ensures clean O(n) lookup without binary search overhead
- **Edge case handling**: Returns first unique_level if avg_shared_level < minimum

#### 2. Asymmetric Score Normalization
- **Pattern**: Different max divisors for different categories
  - Shared cards (GOLD_SHARED, BLUE_SHARED): Normalize by 100
  - Unique cards: Normalize by 10
- **Why this matters**: Reflects game design where unique cards have lower max level (10) vs shared (100)
- **Boundary safety**: Use `min(score, 1.0)` to clamp at max

#### 3. Category Filtering for Progression
- **Pattern**: `[c for c in cards if c.category == category]` for filtering
- **Empty case handling**: Return 0.0 when no cards in category exist
- **Aggregation**: Sum individual scores and divide by count

#### 4. Gating Check as Strict Inequality
- **Pattern**: `card.level < max_allowed` returns True only if strictly below gate
- **At-gate behavior**: Card at gate level CANNOT upgrade (upgrade would exceed gate)
- **Type safety**: Raise ValueError for non-UNIQUE cards to prevent misuse

#### 5. Schedule Accumulation
- **Pattern**: Iterate all schedule entries and sum where `day_key ≤ current_day`
- **Order independence**: No need to sort (loop checks all entries)
- **Empty schedule**: Returns 0 safely

### Test Coverage

#### Floor Lookup Tests (5 tests, 5 passed)
- Exact boundary: `shared=10` → `unique=3` ✓
- Between boundaries: `shared=12` → `unique=3` (floor to 10) ✓
- First boundary: `shared=1` → `unique=1` ✓
- Below first: `shared=0.5` → `unique=1` ✓
- At maximum: `shared=100` → `unique=10` ✓

#### Score Normalization Tests (5 tests, 5 passed)
- Shared at 50%: `50/100 = 0.5` ✓
- Unique at 50%: `5/10 = 0.5` ✓
- Shared at max: `100/100 = 1.0` ✓
- Unique at max: `10/10 = 1.0` ✓
- Shared at min: `0/100 = 0.0` ✓

#### Category Progression Tests (4 tests, 4 passed)
- Gold average: Two cards (50, 100) → `0.75` ✓
- Unique average: Two cards (4, 10) → `0.7` ✓
- Empty category: No cards → `0.0` ✓
- Mixed cards: Correctly filters BLUE_SHARED only → `0.75` ✓

#### Gating Tests (5 tests, 5 passed)
- Below gate: Level 2 < gate 3 → can upgrade ✓
- At gate: Level 3 ≮ gate 3 → cannot upgrade ✓
- Above gate: Level 4 ≮ gate 3 → cannot upgrade ✓
- Gate progression: Increases as shared level increases ✓
- Type safety: Rejects non-UNIQUE cards ✓

#### Unlock Schedule Tests (6 tests, 6 passed)
- Day 35 with {1:8, 30:1} → `8+1=9` ✓
- Day 15 with {1:8, 30:1} → `8` (30 not reached) ✓
- Day 1 start: {1:8, 30:1} → `8` ✓
- Day 0 early: {1:8, 30:1} → `0` ✓
- Complex schedule: {1:8, 30:1, 60:1, 90:1} on day 100 → `11` ✓
- Empty schedule: → `0` ✓

### Code Quality

- **No Streamlit imports**: Module remains simulator-focused
- **No drop algorithm**: Pure gating/progression logic only
- **No upgrade execution**: Only checking/validation functions
- **Type hints**: Complete function signatures with Card, CardCategory, ProgressionMapping
- **Error handling**: Explicit ValueError for contract violations
- **Module dependencies**: Only imports from simulation.models

### Key Conventions for Future Tasks

1. **Gating Pattern**: Always use floor lookup to find applicable level tier
2. **Score Normalization**: Keep separate divisors for different card categories
3. **Empty Cases**: Always return 0.0 or sensible defaults for empty collections
4. **Type Safety**: Raise ValueError for invalid input types rather than silent failures
5. **Schedule Handling**: Iterate all entries without requiring sorted input

## Task 2: Pydantic v2 Data Models & Serialization (Completed)

### Model Architecture

#### 12 Models Implemented
1. **CardCategory** enum: GOLD_SHARED, BLUE_SHARED, UNIQUE (str-based for JSON compatibility)
2. **Card**: Core game object with id, name, category, level (default=1), duplicates (default=0)
3. **StreakState**: Tracks streak_shared, streak_unique + flexible dicts for per-color/hero tracking
4. **GameState**: Complete snapshot with day, cards list, coins, total_bluestars, streaks, logs
5. **PackConfig**: name + card_types_table dict for pack definition
6. **UpgradeTable**: Per-category costs/rewards (duplicate_costs, coin_costs, bluestar_rewards)
7. **DuplicateRange**: Min/max percentiles for duplicate distribution by level
8. **CoinPerDuplicate**: Coin rewards per duplicate by level
9. **ProgressionMapping**: Shared and unique level progressions (floor lookup tables)
10. **SimConfig**: Complete configuration with 15+ fields, sensible defaults
11. **SimResult**: Aggregated results (total_bluestars, coins_earned/spent, daily_snapshots)

### Pydantic v2 Patterns Applied

#### 1. JSON Serialization API
- **Use model_dump_json()**: NOT json.dumps() or .dict()
- **Use model_validate_json()**: NOT parse_obj() or parse_raw()
- **Why**: Native Pydantic v2 methods with better type handling
- **Tested**: All 11 models + complex nested structures verified

#### 2. Default Values with Field()
```python
level: int = Field(default=1, description="Card level, defaults to 1")
duplicates: int = Field(default=0, description="Number of duplicates")
```
- **Pattern**: Use Field() for all defaults, not bare =
- **Benefit**: Enables description strings for documentation
- **Type Safety**: Pydantic validates default types at model definition

#### 3. Complex Types
- **Dict with typed keys/values**: Dict[str, int], Dict[CardCategory, UpgradeTable]
- **List composition**: List[Card], List[int], List[float]
- **Optional**: Optional[int] for mc_runs field
- **Any type**: For flexible log entries (daily_snapshots: List[Any])

#### 4. Factory Defaults for Mutables
```python
streak_per_color: Dict[str, int] = Field(default_factory=dict)
cards: List[Card] = Field(default_factory=list)
```
- **Pattern**: Use default_factory=dict/list, NOT default={}
- **Why**: Prevents shared mutable state between instances
- **Pydantic v2 requirement**: Explicit factory needed

### Test Coverage: 29 Tests, 100% Pass Rate

#### By Category
- **CardCategory (1 test)**: Enum value verification
- **Card (4 tests)**: Defaults, explicit values, JSON round-trip, field completeness
- **StreakState (3 tests)**: Basic, with dicts, JSON serialization
- **GameState (3 tests)**: Basic, with cards, complex JSON serialization
- **PackConfig (2 tests)**: Basic, JSON serialization
- **UpgradeTable (2 tests)**: Basic, JSON serialization
- **DuplicateRange (2 tests)**: Basic, JSON serialization
- **CoinPerDuplicate (2 tests)**: Basic, JSON serialization
- **ProgressionMapping (2 tests)**: Basic, JSON serialization
- **SimConfig (3 tests)**: Defaults, custom values, JSON serialization with nested objects
- **SimResult (3 tests)**: Basic, with data, JSON serialization

#### Integration Tests (2 tests)
- **Complex GameState**: Nested Card list + StreakState + mixed dicts → JSON round-trip
- **Full SimConfig**: Multiple PackConfigs + UpgradeTable dict + nested ProgressionMapping → JSON round-trip

### Key Conventions Established

1. **Enum for Categories**: str-based enum (CardCategory inherits str) for JSON compatibility
2. **Field Descriptions**: All defaults documented with description parameter
3. **Factory Defaults**: Mutable types use default_factory
4. **JSON Preservation**: Model round-trip (serialize → deserialize) returns exact equality
5. **No Type Coercion**: Pydantic validates strict types (int, float, str, enum)

### Architecture Decisions

- **CardCategory as string enum**: Enables JSON serialization without custom serializers
- **Flexible dict fields**: streak_per_color, daily_log use Any/dict for extensibility
- **Flat model hierarchy**: No deeply nested inheritance, easy to modify per-task needs
- **Default rate constants**: base_shared_rate=0.70, base_unique_rate=0.30 baked into SimConfig

### Code Quality

✅ **Zero Streamlit imports**: simulation/models.py is Streamlit-free
✅ **No business logic**: Data structures only, no simulation algorithms
✅ **Complete test coverage**: All models + defaults + serialization tested
✅ **Pydantic v2 native**: Uses model_dump_json/model_validate_json (not v1 API)
✅ **Type-safe defaults**: All 11 models validate on instantiation
✅ **Extensible design**: Dict fields allow game mechanics to expand

### Build Verification

✅ pytest tests/test_models.py -v → 29/29 PASSED
✅ grep for streamlit imports in simulation/ → 0 results
✅ All models instantiate and serialize without errors
✅ JSON round-trip equality verified for complex nested structures

## 2026-02-18 Task 6: Coin Economy System

### Key Learnings

**0-Indexing Pattern**: Upgrade costs and coin rates use 0-indexed lookup: `table[card.level - 1]`
- Card level 1-100 (human-friendly) → index 0-99 (array)
- Critical for correct cost/income calculation

**Maxed Card Handling**: Cards at max level get flat coin reward (coins_per_dupe[0])
- GOLD_SHARED/BLUE_SHARED: max 100
- UNIQUE: max 10
- No upgrades possible at max level

**CoinLedger Design**: In-memory transaction ledger with atomic spend validation
- spend() returns False if insufficient balance
- Balance unchanged on failed spend (all-or-nothing)
- Transactions only recorded on successful spend

**daily_summary() Returns**: 
- total_income, total_spent aggregated for day
- balance: current cumulative balance (not per-day)
- Useful for daily logs and financial tracking

### Implementation Conventions

1. Always use 0-indexed lookup: `coin_costs[card.level - 1]`
2. Check maxed status before looking up tables (avoid index out of range)
3. CoinTransaction is immutable dataclass (audit trail)
4. CoinLedger methods side-effect balance (transaction recorded iff spend succeeds)

### Testing Pattern

Used pytest fixtures with SimConfig containing:
- UpgradeTable: category + duplicate_costs + coin_costs + bluestar_rewards
- CoinPerDuplicate: category + coins_per_dupe (list indexed by level-1)
- ProgressionMapping: shared_levels + unique_levels for unlock gating

27 tests covering:
- Income calculation (7 tests)
- Upgrade cost lookup (7 tests)
- Affordability check (4 tests)
- Ledger operations (9 tests, including daily summaries)

All PASSED ✓

## Task 4: Pack System Implementation

**Key findings**:
- CardPull dataclass is lightweight: just pack_name (str) and pull_index (int)
- Floor lookup for card_types_table: use max(keys where key <= total_unlocked)
- Deterministic mode: Python's round() uses banker's rounding (2.5→2, 3.5→4)
- MC mode: numpy.random.poisson() for stochastic pack counts
- rng parameter is passed but unused in current implementation (reserved for future card drop algorithm seeding)
- Edge case: 0 packs/day handled correctly in both deterministic and MC modes
- Floor lookup test scenario (0 unlocked, table {0:1, 10:2, 20:3}): correctly returns 1 card type

**Architecture notes**:
- process_packs_for_day returns flat list of CardPull objects (one per card, not per pack)
- Total pulls = sum(packs_count[i] * card_types[i]) for each pack type
- pack_averages dict keys must match pack config names
- Separation of concerns: no card selection here (that's the drop algorithm in Task 7-8)

**Tested scenarios**:
- 0 packs (deterministic + MC) → 0 pulls ✓
- Rounding behavior: 2.4→2, 2.5→2, 2.6→3 ✓
- Multiple pack types with different card yields ✓
- Floor lookup at exact threshold, between thresholds, below min ✓
- Poisson distribution reproducibility with seed ✓

## Task 9: Upgrade Engine Implementation

### Greedy Algorithm Behavior
- Upgrade loop continues until no more upgrades possible
- Single card can upgrade multiple times in one `attempt_upgrades()` call
- Example: Card with 100 dupes + 500 coins upgrades twice (2×50 dupes, 2×200 coins)
- Test expectations must account for multi-upgrade behavior

### Priority Ordering Implementation
- Three-tier priority: UNIQUE > GOLD_SHARED > BLUE_SHARED
- Within each category: lowest level first (catch-up mechanic)
- Implementation: Sort three lists separately, concatenate in priority order
- Loop restarts candidate scan after each upgrade (priorities may shift)

### Index Arithmetic for Bluestar Rewards
- Critical pattern: `bluestar_rewards[card.level]` where card.level is BEFORE increment
- bluestar_rewards[i] = reward for reaching level i+1
- For level 5→6 upgrade: use bluestar_rewards[5] (0-indexed)
- This is DIFFERENT from dupe/coin costs which use [card.level - 1]

### Progression Gating Integration
- `compute_category_progression()` returns 0.0-1.0 normalized score
- Must multiply by 100 to convert to avg shared level for gating check
- Formula: avg_shared_level = ((gold_prog + blue_prog) / 2.0) * 100.0
- Gating only applies to UNIQUE cards

### Resource Deduction Order
- Check all 4 conditions BEFORE executing upgrade
- Execute in order: deduct dupes → spend coins → increment level → award bluestars
- Assert on coin spend success (should never fail after can_afford check)

### Test Coverage Patterns
- 11 tests covering: success, blocking conditions (3), priority (2), loops, accumulation, maxed cards (2)
- Tests validate greedy loop behavior (multiple upgrades per call)
- Evidence files capture key scenarios (success, priority, gating)

## Task 7: Phase 1 Drop Algorithm (Rarity Decision)

### Implementation Patterns

**5-Step Algorithm Structure**
- Step-by-step comments map directly to Revamp Master Doc flowchart
- Each step is mathematically isolated for debugging
- Progression → Gap Adjustment → Streak Penalty → Normalize → Roll

**Key Formula Insights**
- Gap adjustment uses exponential balancing: `base_rate * (GAP_BASE ^ Gap)`
- Asymmetric gap application: positive gap boosts shared, negative gap boosts unique
- Streak decay is exponential: `weight * (decay_rate ^ streak_count)`
- Unique streak decay (0.3) is 2x more aggressive than shared (0.6)

**Function Signature Pattern**
```python
decide_rarity(
    game_state: GameState,
    config: SimConfig,
    streak_state: StreakState,
    rng: Optional[Random] = None,  # None = deterministic mode
) -> CardCategory
```

**Deterministic vs Monte Carlo**
- `rng=None`: Returns majority category (ProbShared >= 0.5 → GOLD_SHARED)
- `rng=Random(seed)`: Weighted random roll for statistical simulation
- Both modes use identical probability calculations

### Dependencies Discovered

**Progression Module**
- `compute_category_progression()` requires 3 args: `(cards, category, mapping)`
- Task spec showed 2 args - corrected during implementation
- Returns 0.0 for empty categories (safe default)

**ProgressionMapping Required**
- SimConfig must include `progression_mapping` for progression calculations
- Test fixtures must provide valid `ProgressionMapping` with shared/unique levels

### Test Design Patterns

**Statistical Test Strategy**
- 10,000 Monte Carlo rolls with seeded RNG (seed=42)
- Tolerance bands: ±3% for balanced state (0.67-0.73 for 70% target)
- Assertions use probability ranges not exact values

**Edge Case Coverage**
- Empty card list: Returns base rates (70/30)
- Deterministic mode: Always chooses majority
- Streak alternation: Correctly resets counters

### Mathematical Verification

**Balanced State (Gap=0, No Streaks)**
- Expected: 70% shared, 30% unique
- Observed: Within 0.67-0.73 range (verified)

**Positive Gap (Unique Ahead by 0.6)**
- Expected: System catches up shared → ProbShared > 75%
- Observed: ~80.9% (gap adjustment working)

**Negative Gap (Shared Ahead by 0.6)**
- Expected: System catches up unique → ProbUnique > 35%
- Observed: ~43.8% (gap adjustment working)

**Streak Penalty Effects**
- Shared streak=3: ProbShared drops from 70% to ~33.5%
- Unique streak=3: ProbUnique drops from 30% to ~1.1%
- Unique streaks are penalized 3.6x more severely

### Gotchas and Notes

**Return Type**
- Function returns `CardCategory.GOLD_SHARED` not generic "SHARED"
- Phase 2 (Task 8) will handle Gold vs Blue selection
- Current implementation uses GOLD_SHARED as placeholder for any shared card

**Streak Update Isolation**
- `update_rarity_streak()` only updates rarity streaks
- Color and hero streaks preserved (updated in Phase 2)
- Returns new StreakState (immutable pattern)

**Constants Export**
- STREAK_DECAY_SHARED, STREAK_DECAY_UNIQUE, GAP_BASE at module level
- Required for test verification and future tuning

### Quality Metrics

- Files created: 2 (drop_algorithm.py, test_drop_algorithm.py)
- Tests implemented: 11 (exceeded minimum 7 requirement)
- Test coverage: All major scenarios + edge cases
- LSP diagnostics: Only warnings (type inference), no errors
- All tests: PASSED ✅

### Evidence Artifacts

Created verification files:
- task-7-balanced-rates.txt: Statistical distribution verification
- task-7-gap-adjustment.txt: Gap balancing behavior
- task-7-streak-penalty.txt: Streak penalty calculations


## Task 8: Card Selection Within Category (Phase 2)

### Implementation Summary
Added 5 functions implementing Phase 2 of the drop algorithm:
- `select_shared_card()`: Weighted selection from Gold + Blue pools
- `select_unique_card()`: Top-10 filtering + weighted selection
- `update_card_streak()`: Color/hero streak tracking
- `compute_duplicates_received()`: Percentile-based duplicate calculation
- `perform_card_pull()`: Full orchestration (Phase 1 → Phase 2 → duplicates → coins)

### Key Patterns

**Weighted Selection Formula:**
```python
base_weight = 1.0 / (card.level + 1)
final_weight = base_weight * (0.6 ** streak)
```

**Dict Keys for Streaks:**
- Color streaks: Use `card.category.value` (e.g., "GOLD_SHARED", "BLUE_SHARED")
- Hero streaks: Use `card.id` (e.g., "hero_1")

**Random.choices() for MC mode:**
```python
rng.choices(cards, weights=weights, k=1)[0]
```

**Deterministic mode (rng=None):**
```python
max_idx = weights.index(max(weights))
return cards[max_idx]
```

### Critical Edge Cases

1. **Maxed Cards**: Return 0 duplicates when at max level
2. **Top-10 Filtering**: Only applies to unique cards, not shared
3. **Streak Reset**: When selecting a card, increment its streak and reset ALL others in same category
4. **0-indexed Tables**: All cost/range tables use level-1 as index

### Test Coverage
21 total tests (11 Phase 1 + 10 Phase 2):
- Level weighting distribution (1000 MC runs)
- Color streak penalty (Gold vs Blue)
- Hero streak penalty (unique cards)
- Deterministic vs MC mode
- Maxed card edge case
- Percentile range midpoint calculation
- Full pull integration
- Streak update logic (gold/blue/hero)

### Integration Points
- Imports `compute_coin_income()` from coin_economy module
- Returns tuple: `(Card, duplicates, coins, updated_streak_state)`
- Orchestrator can chain calls by passing updated_streak_state

### Performance Notes
- Weighted selection is O(n) where n = number of cards in category
- Top-10 filtering reduces unique candidate pool from 100+ to 10
- Sorting by level is O(n log n) but runs once per pull


## Task 10: Simulation Orchestrator

### Implementation Patterns

**Daily Loop Order (CRITICAL)**
Exact sequence matters for correctness:
1. Check unlock schedule → add new unique cards if needed
2. Process packs for day → returns list[CardPull]
3. Sequential card pulls with streak propagation → MUST pass updated_streak_state to next call
4. Attempt upgrades (greedy loop until exhausted)
5. Record DailySnapshot with 10 fields

**Streak State Propagation (CRITICAL)**
```python
for card_pull in card_pulls:
    card, dupes, coins, updated_streak = perform_card_pull(game_state, config, streak_state, rng)
    streak_state = updated_streak  # MUST propagate for next iteration
```
Forgetting this breaks the streak penalty system across pulls within a single day.

**Initial State Setup**
- 9 Gold Shared cards (gold_1 to gold_9)
- 14 Blue Shared cards (blue_1 to blue_14)
- Initial unique cards from day 1 unlock schedule (hero_1 to hero_N)
- All cards start at level 1, 0 duplicates
- CoinLedger starts at 0 balance
- StreakState all zeroes

**Unlock Schedule Logic**
```python
unlocked_count = get_unlocked_unique_count(day, config.unique_unlock_schedule)
current_unique_count = len([c for c in game_state.cards if c.category == CardCategory.UNIQUE])
if unlocked_count > current_unique_count:
    # Add new unique cards (hero_{i} for i in range(current+1, unlocked+1))
```

### Integration Discoveries

**API Signature Gotcha**
- `get_unlocked_unique_count(day, schedule)` — day FIRST, schedule SECOND
- Task spec example showed it backwards — corrected during implementation
- All other engine functions matched their documented signatures

**CardPull is Metadata Only**
- CardPull contains pack_name + pull_index (no card reference)
- Actual card selection happens in `perform_card_pull()`
- This is lightweight by design for Monte Carlo runs

**DailySnapshot Field Calculations**
```python
summary = coin_ledger.daily_summary(day)
coins_earned_today = summary["total_income"]
coins_spent_today = summary["total_spent"]

bluestars_earned_today = sum(e.bluestars_earned for e in upgrade_events)

category_avg_levels = {}
for category in [CardCategory.GOLD_SHARED, CardCategory.BLUE_SHARED, CardCategory.UNIQUE]:
    cat_cards = [c for c in game_state.cards if c.category == category]
    if cat_cards:
        category_avg_levels[category.value] = sum(c.level for c in cat_cards) / len(cat_cards)
    else:
        category_avg_levels[category.value] = 0.0
```

**Aggregate Statistics**
- total_bluestars: Direct from game_state.total_bluestars
- total_coins_earned: Sum all income transactions across all days
- total_coins_spent: Sum all spend transactions across all days
- total_upgrades: Dict mapping card_id → count of upgrades

### Performance Notes

**100-Day Simulation: 0.12 seconds**
- Target was < 30 seconds — achieved 250× faster
- Deterministic mode (rng=None) has minimal overhead
- No performance bottlenecks detected
- Full test suite (149 tests) completes in 0.53 seconds

**Scaling Characteristics**
- Linear time complexity: O(days × pulls_per_day × cards)
- Daily upgrade loop: O(cards) for candidate scan, repeats until exhausted
- Snapshot recording: O(cards) for category averages
- No expensive operations (no sorting in hot path, no deep copies)

### Test Coverage

**8 Tests Implemented (7 required + 1 bonus)**
1. test_oneday_simulation: Validates all snapshot fields non-negative ✓
2. test_duplicates_accumulate: Verifies card levels increase over days ✓
3. test_upgrades_fire: Confirms upgrades execute when resources available ✓
4. test_unlock_schedule: Validates {1:8, 5:2} schedule adds cards on correct days ✓
5. test_bluestar_accounting: Ensures total = sum of daily earnings ✓
6. test_coin_balance: Verifies balance = income - spent ✓
7. test_performance_100days: Confirms < 30s (actual: 0.12s) ✓
8. test_initial_state_setup: Validates card counts (9+14+8) ✓

**Key Test Patterns**
- Use full_config fixture with all required tables
- Deterministic mode (rng=None) for reproducible assertions
- Performance tests use time.time() for elapsed measurement
- Unlock schedule test checks multiple days (1, 4, 5, 6) to verify persistence

### Architecture Quality

**File Size: 253 lines**
- Target: < 200 lines (missed by 53 lines due to detailed field calculations)
- Still well under 300 hard limit
- Could be reduced by extracting snapshot calculation to helper function

**Dependencies**
- Imports from 5 engine modules (pack_system, drop_algorithm, upgrade_engine, coin_economy, progression)
- All module integrations work correctly on first try (after API signature fix)

**No Regressions**
- All 141 existing tests still pass ✓
- Total test count: 149 (8 new orchestrator tests added)
- LSP diagnostics: Only warnings (type hints, deprecations) — no errors

### Critical Learnings for Next Tasks

**For Monte Carlo (Task 11)**
- Pass `rng=Random(seed)` instead of `rng=None` for stochastic mode
- All engine modules already support rng parameter
- Orchestrator signature ready: `run_simulation(config, rng=Optional[Random])`

**For Dashboard (Tasks 14-15)**
- DailySnapshot has all 10 fields needed for visualization
- SimResult aggregates are ready for summary cards
- category_avg_levels dict ready for progression charts

**Streak State Critical Pattern**
- Within a day: Propagate streak_state across sequential pulls
- Across days: streak_state persists in orchestrator scope
- Forgetting this breaks weighted selection algorithm

### Evidence Files Created

- `.sisyphus/evidence/task-10-oneday.txt`: 1-day snapshot validation
- `.sisyphus/evidence/task-10-performance.txt`: 100-day timing (0.12s)
- `.sisyphus/evidence/task-10-unlock-schedule.txt`: Unlock schedule verification

