# Architectural Decisions

This file tracks architectural choices made during implementation.

Format: Append entries as `## [TIMESTAMP] Task: {task-id}\n{content}`

## 2026-02-18 Task 3: Config Loader & JSON Fixtures

### JSON Structure Decisions

1. **Pack Configs (pack_configs.json)**
   - Structure: `{ "packs": [{ "name": "PackN", "card_types_table": {...} }] }`
   - 9 packs with identical placeholder card_types_table
   - Keys in card_types_table are strings in JSON, converted to integers by Pydantic

2. **Upgrade Tables (upgrade_tables.json)**
   - Dictionary keyed by category (GOLD_SHARED, BLUE_SHARED, UNIQUE)
   - Each category has: duplicate_costs[], coin_costs[], bluestar_rewards[]
   - Shared: 99 levels (indices 0-98) with escalating values
   - Unique: 9 levels (indices 0-8) with escalating values
   - Escalation pattern: 1, 2, 3, ... (1-indexed for costs, scaled for coins)

3. **Duplicate Ranges (duplicate_ranges.json)**
   - 3 categories, each with min_pct[] and max_pct[] arrays
   - Arrays lengths match corresponding upgrade tables
   - Used placeholder pattern with slight escalation from base 0.05/0.15

4. **Coin Per Duplicate (coin_per_duplicate.json)**
   - 3 categories, each with coins_per_dupe[] array
   - Simple 1-indexed escalation: 1, 2, 3, ..., 99 for shared; 1-9 for unique

5. **Progression Mapping (progression_mapping.json)**
   - Implemented as dict: `{ "shared_to_unique": { "1": 1, "5": 2, ... } }`
   - Config loader converts to ProgressionMapping(shared_levels=[], unique_levels=[])
   - Exact mapping from spec verified: shared [1,5,10,15,25,45,60,70,80,90,100] → [1,2,3,4,5,6,7,8,9,10,10]

6. **Unique Unlock Schedule (unique_unlock_schedule.json)**
   - Dictionary keyed by day (string in JSON, converted to int)
   - Mapping: {1: 8, 30: 1, 60: 1, 90: 1}

7. **Pack Averages (pack_averages.json)**
   - Simple dict: { "Pack1": 1.0, "Pack2": 1.0, ... }
   - 9 entries matching pack_configs.json

### Config Loader Implementation (simulation/config_loader.py)

- Uses relative path resolution via `__file__` for portability
- Single entry point: `load_defaults() -> SimConfig`
- Handles JSON → Pydantic model conversion for all data types
- Progression mapping transformation: dict → separate shared/unique level lists
- String→int key conversion for schedule (JSON limitation)

### Testing Strategy (tests/test_config_loader.py)

- 11 comprehensive tests covering all data structures
- Tests verify: count of items, length of arrays, correct values, field population
- Test failures caught Pydantic key type conversion (string→int for dict keys)

### Known Limitations

- Card_types_table uses fixed placeholder values {31:3, 40:4, 50:5}
- All pack averages are placeholder 1.0 values
- Ranges use synthetic escalation pattern, not derived from game data
- These are all intentional placeholders awaiting real game data
