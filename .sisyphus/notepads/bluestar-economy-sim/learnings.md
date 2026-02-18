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
