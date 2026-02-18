# Bluestar Economy Simulator

## TL;DR

> **Quick Summary**: Build a Python/Streamlit game economy simulator that models the complete Bluestar progression loop — from pack opening through a sophisticated weighted card drop algorithm, to duplicate accumulation, coin/duplicate-gated upgrades, and Bluestar rewards. Full dashboard with day-by-day tracking, configurable lookup tables, and URL-based config sharing for team collaboration.
> 
> **Deliverables**:
> - Pure Python simulation engine (card drop algorithm, upgrade engine, coin economy)
> - Streamlit web UI with editable config tables and interactive dashboard
> - Automated test suite (pytest) validating all simulation math
> - Cloud deployment on Streamlit Cloud
> - URL-based config sharing for colleagues
> 
> **Estimated Effort**: Large
> **Parallel Execution**: YES — 5 waves
> **Critical Path**: Data Models → Drop Algorithm → Simulation Orchestrator → Dashboard UI → Integration Tests

---

## Context

### Original Request
Build a game economy simulator centered on "Bluestars" — the core power currency earned by upgrading cards. Cards come from packs (9 types), with a sophisticated weighted drop algorithm. The system has 3 card categories (Unique, Gold Shared, Blue Shared) with different upgrade tables, coin costs, and Bluestar rewards. Must support both deterministic and Monte Carlo simulation modes, be configurable via editable tables, and shareable between colleagues.

### Interview Summary
**Key Discussions**:
- **Card drop algorithm**: NOT a simple 30/70 split — sophisticated weighted system with progression gap balancing (1.5^Gap), streak penalties (0.6^Streak / 0.3^Streak), and per-card level weighting (1/(Level+1)). Fully detailed in Revamp Master Doc.
- **Card levels are INDIVIDUAL**: Each card tracks its own level. The drop algorithm's weighting naturally creates catch-up for stragglers.
- **Coin economy is complex**: Coins come ONLY from pack opening (per-duplicate income varies by category/level). Single shared pool. Spent on upgrades. Can bottleneck progression.
- **Upgrade priority**: Unique > Gold Shared > Blue Shared when coins limited. Auto-upgrade (greedy). Multiple upgrades per day allowed.
- **Pack processing**: Sequential within a day — order matters as levels change between packs.
- **Progression gating**: Shared↔Unique level mapping table GATES unique upgrades (unique can't level past mapped equivalent).
- **Tech**: Streamlit (Python), cloud deploy, URL sharing. No real-time co-editing needed.
- **Testing**: Automated tests for simulation math (pytest).
- **Simulation modes**: Deterministic (expected values) + Monte Carlo (N random trials). Toggle between.

**Research Findings**:
- Streamlit Cloud: ~1GB memory limit, ephemeral storage, free hosting
- `st.data_editor` with `column_config` for validated editable tables
- `st.tabs` (not expanders) for table groups — expanders compute even when collapsed
- `@st.cache_data` with single config hash key (not 15 separate params)
- Welford's online algorithm for incremental MC statistics (avoid storing all runs)
- URL config: `st.query_params` with gzip + base64 encoded JSON
- Plotly for interactive charts (native Streamlit support)

### Metis Review
**Identified Gaps** (addressed):
- Card level uniformity contradiction → RESOLVED: individual per-card levels confirmed
- Missing default data → User will provide all default values for tables
- Upgrade priority between categories → RESOLVED: Unique > Gold > Blue
- Pack order within day → RESOLVED: sequential, order matters
- Maxed card behavior → RESOLVED: flat coin reward, no dupes
- Streak reset → RESOLVED: hard reset to 0
- Coin pool → RESOLVED: single shared pool
- Progression score formula → Uses mapping table normalization
- MC memory concerns → Welford's online algorithm, cap at 500 runs

---

## Work Objectives

### Core Objective
Build a configurable Bluestar economy simulator that faithfully implements the Revamp Master Doc card drop algorithm, tracks per-card state for 31+ cards, models dual-resource progression (duplicates + coins), and provides a rich dashboard for analyzing day-by-day Bluestar accumulation over N days.

### Concrete Deliverables
- `simulation/` — Pure Python engine package (zero Streamlit imports)
  - `models.py` — Data models (Card, GameState, SimConfig, etc.)
  - `drop_algorithm.py` — Full Revamp Master Doc algorithm
  - `upgrade_engine.py` — Upgrade logic with gating + coin management
  - `coin_economy.py` — Coin income/spending tracking
  - `orchestrator.py` — Day-by-day simulation loop
  - `monte_carlo.py` — MC runner with Welford's statistics
- `data/defaults/` — JSON fixture files for all configurable tables
- `app.py` — Streamlit main app
- `pages/` — Streamlit pages (config editor, dashboard, simulation controls)
- `tests/` — Comprehensive pytest suite
- `requirements.txt` — Dependencies
- `README.md` — Setup & usage guide
- `.streamlit/config.toml` — Streamlit cloud config

### Definition of Done
- [ ] `pytest tests/ -v` → all tests pass (0 failures)
- [ ] `streamlit run app.py --server.headless true` → serves HTTP 200 within 10s
- [ ] Deterministic 100-day simulation completes in < 30 seconds
- [ ] Monte Carlo 100-run × 100-day simulation completes in < 120 seconds
- [ ] URL config round-trip: encode → share → decode produces identical config
- [ ] All 4 dashboard charts render with simulation results
- [ ] Deployable to Streamlit Cloud

### Must Have
- Full Revamp Master Doc card drop algorithm (exact formulas)
- Per-card state tracking (individual levels, not category averages)
- 3 card categories with distinct upgrade tables (dupes, coins, bluestars)
- 9 configurable pack type tables
- Progression gating via level mapping table
- Coin economy fully modeled (income, spending, bottleneck tracking)
- Deterministic AND Monte Carlo simulation modes
- Editable config tables in UI with validation
- URL-based config sharing (gzip + base64)
- 4 dashboard charts: Bluestar curve, card progression, coin flow, pack ROI
- Automated pytest suite for simulation math
- Restore Defaults button for every table

### Must NOT Have (Guardrails)
- Alternative upgrade strategies (greedy ONLY — no "optimal" or "save-for-later")
- Comparison mode (side-by-side configs)
- Data export (CSV/Excel)
- User accounts or authentication
- Database or ORM (JSON serialization only)
- Per-individual-card charts (category-level aggregation only in visualizations)
- Animation/replay of day-by-day simulation
- Pack optimization recommendations ("which packs to buy")
- `st.expander` for config tables (use `st.tabs` — expanders compute content when collapsed)
- Passing 15 separate table parameters to cached functions (single config hash key)
- Storing all MC run results simultaneously (use Welford's incremental statistics)

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: NO (greenfield)
- **Automated tests**: YES — Tests alongside implementation (simulation math is critical)
- **Framework**: pytest
- **Strategy**: Write tests for each simulation module. Hand-calculated reference scenarios as ground truth fixtures.

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

| Deliverable Type | Verification Tool | Method |
|------------------|-------------------|--------|
| Simulation engine modules | Bash (pytest) | Run tests, assert exact numeric outputs |
| Streamlit UI | Bash (streamlit run + curl health check) | Launch app, verify HTTP 200 |
| Config tables | Bash (pytest) | Serialize/deserialize round-trip tests |
| Dashboard charts | Bash (streamlit run) | Verify app doesn't crash with sample data |
| URL sharing | Bash (pytest) | Encode/decode config, assert equality |

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation — Start Immediately, 6 parallel tasks):
├── Task 1: Project scaffolding + config [quick]
├── Task 2: Data models (Card, GameState, SimConfig) [quick]
├── Task 3: Default data JSON fixtures (placeholder structure) [quick]
├── Task 4: Pack system module [quick]
├── Task 5: Progression mapping + gating logic [quick]
└── Task 6: Coin economy module [quick]

Wave 2 (Core Algorithm — After Wave 1, 3 parallel tasks):
├── Task 7: Card drop algorithm — Phase 1 rarity decision (depends: 2, 5) [deep]
├── Task 8: Card drop algorithm — Phase 2 card selection (depends: 2, 7) [deep]
└── Task 9: Upgrade engine (depends: 2, 5, 6) [deep]

Wave 3 (Integration — After Wave 2, 2 parallel tasks):
├── Task 10: Simulation orchestrator — deterministic mode (depends: 4, 7, 8, 9) [deep]
└── Task 11: Monte Carlo runner with Welford statistics (depends: 10) [ultrabrain]

Wave 4 (UI — After Wave 3, 4 parallel tasks):
├── Task 12: Streamlit config editor UI — pack & upgrade tables (depends: 2, 3) [unspecified-high]
├── Task 13: Streamlit simulation controls & URL sharing (depends: 10, 11) [unspecified-high]
├── Task 14: Dashboard — Bluestar curve + card progression charts (depends: 10) [visual-engineering]
└── Task 15: Dashboard — coin economy flow + pack ROI charts (depends: 10) [visual-engineering]

Wave 5 (Final — After Wave 4, 3 parallel tasks):
├── Task 16: Integration tests + edge cases (depends: 10, 11, 12, 13) [deep]
├── Task 17: Deployment prep (Streamlit Cloud + README) (depends: all) [quick]
└── Task 18: Comprehensive QA (depends: all) [unspecified-high]

Wave FINAL (After ALL tasks — independent review, 4 parallel):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
└── Task F4: Scope fidelity check (deep)

Critical Path: Task 1 → Task 2 → Task 7 → Task 8 → Task 10 → Task 11 → Task 13 → Task 16 → F1-F4
Parallel Speedup: ~65% faster than sequential
Max Concurrent: 6 (Wave 1)
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|------------|--------|------|
| 1 | — | 2-6 | 1 |
| 2 | 1 | 7, 8, 9, 12 | 1 |
| 3 | 1 | 12 | 1 |
| 4 | 1 | 10 | 1 |
| 5 | 1 | 7, 9 | 1 |
| 6 | 1 | 9 | 1 |
| 7 | 2, 5 | 8, 10 | 2 |
| 8 | 2, 7 | 10 | 2 |
| 9 | 2, 5, 6 | 10 | 2 |
| 10 | 4, 7, 8, 9 | 11, 13, 14, 15, 16 | 3 |
| 11 | 10 | 13, 16 | 3 |
| 12 | 2, 3 | 16 | 4 |
| 13 | 10, 11 | 16 | 4 |
| 14 | 10 | 18 | 4 |
| 15 | 10 | 18 | 4 |
| 16 | 10, 11, 12, 13 | 17 | 5 |
| 17 | all | F1-F4 | 5 |
| 18 | all | F1-F4 | 5 |

### Agent Dispatch Summary

| Wave | # Parallel | Tasks → Agent Category |
|------|------------|----------------------|
| 1 | **6** | T1-T6 → `quick` |
| 2 | **3** | T7-T8 → `deep`, T9 → `deep` |
| 3 | **2** | T10 → `deep`, T11 → `ultrabrain` |
| 4 | **4** | T12-T13 → `unspecified-high`, T14-T15 → `visual-engineering` |
| 5 | **3** | T16 → `deep`, T17 → `quick`, T18 → `unspecified-high` |
| FINAL | **4** | F1 → `oracle`, F2-F3 → `unspecified-high`, F4 → `deep` |

---

## TODOs

- [x] 1. Project Scaffolding + Configuration

  **What to do**:
  - Initialize git repository
  - Create directory structure: `simulation/`, `data/defaults/`, `tests/`, `pages/`, `.streamlit/`
  - Create `requirements.txt` with: streamlit, plotly, numpy, pandas, pytest, pydantic
  - Create `.streamlit/config.toml` with server config (headless, port, theme)
  - Create `simulation/__init__.py` (empty)
  - Create `app.py` with minimal "Hello World" Streamlit page
  - Create `README.md` with project description, setup instructions (pip install, streamlit run)
  - Create `.gitignore` (Python standard: __pycache__, .venv, .env, *.pyc)
  - Verify: `pip install -r requirements.txt && streamlit run app.py --server.headless true` serves HTTP 200

  **Must NOT do**:
  - No simulation logic yet
  - No UI components beyond placeholder
  - No database setup

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple file creation, no complex logic
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `playwright`: No browser testing needed for scaffolding

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3, 4, 5, 6)
  - **Blocks**: Tasks 2-6 (all need project structure)
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `Revamp Master Doc.jpg` — Reference image for understanding the game system being simulated

  **External References**:
  - Streamlit docs: https://docs.streamlit.io/get-started/installation — Setup guide
  - Streamlit Cloud config: https://docs.streamlit.io/deploy/streamlit-community-cloud — Deployment requirements

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Project structure exists
    Tool: Bash
    Preconditions: Fresh clone of repository
    Steps:
      1. Run: ls -la simulation/ data/defaults/ tests/ pages/ .streamlit/
      2. Assert: all directories exist
      3. Run: cat requirements.txt
      4. Assert: contains "streamlit", "plotly", "numpy", "pandas", "pytest", "pydantic"
    Expected Result: All directories and files present
    Failure Indicators: "No such file or directory" for any path
    Evidence: .sisyphus/evidence/task-1-project-structure.txt

  Scenario: App launches successfully
    Tool: Bash
    Preconditions: pip install -r requirements.txt completed
    Steps:
      1. Run: timeout 15 streamlit run app.py --server.headless true &
      2. Wait 5 seconds
      3. Run: curl -s -o /dev/null -w "%{http_code}" http://localhost:8501
      4. Assert: HTTP status code is "200"
      5. Kill streamlit process
    Expected Result: HTTP 200 returned within 10 seconds
    Failure Indicators: Connection refused, HTTP 500, timeout
    Evidence: .sisyphus/evidence/task-1-app-launch.txt
  ```

  **Commit**: YES
  - Message: `chore: scaffold project structure with deps and config`
  - Files: `requirements.txt, .streamlit/config.toml, app.py, README.md, .gitignore, simulation/__init__.py`
  - Pre-commit: `pip install -r requirements.txt`

- [x] 2. Data Models (Card, GameState, SimConfig)

  **What to do**:
  - Create `simulation/models.py` with Pydantic models:
    - `CardCategory` enum: GOLD_SHARED, BLUE_SHARED, UNIQUE
    - `Card` model: id, name, category (CardCategory), level (int, default=1), duplicates (int, default=0)
    - `StreakState` model: streak_shared (int), streak_unique (int), streak_per_color (dict[str, int]), streak_per_hero (dict[str, int])
    - `GameState` model: day (int), cards (list[Card]), coins (int), total_bluestars (int), streak_state (StreakState), unlock_schedule (dict), daily_log (list)
    - `PackConfig` model: name (str), card_types_table (dict[int, int]) — maps total_unlocked → card_types_yielded
    - `UpgradeTable` model: category (CardCategory), duplicate_costs (list[int]), coin_costs (list[int]), bluestar_rewards (list[int])
    - `DuplicateRange` model: category (CardCategory), min_pct (list[float]), max_pct (list[float]) — per level
    - `CoinPerDuplicate` model: category (CardCategory), coins_per_dupe (list[int]) — per level
    - `ProgressionMapping` model: shared_levels (list[int]), unique_levels (list[int])
    - `SimConfig` model: packs (list[PackConfig]), upgrade_tables (dict[CardCategory, UpgradeTable]), duplicate_ranges (dict[CardCategory, DuplicateRange]), coin_per_duplicate (dict[CardCategory, CoinPerDuplicate]), progression_mapping (ProgressionMapping), unique_unlock_schedule (dict[int, int]) — day→count, pack_averages (dict[str, float]) — pack_name→daily_avg, num_days (int), mc_runs (int, optional), base_shared_rate (float, default=0.70), base_unique_rate (float, default=0.30), max_shared_level (int, default=100), max_unique_level (int, default=10)
    - `SimResult` model: daily_snapshots (list), total_bluestars (int), total_coins_earned (int), total_coins_spent (int), total_upgrades (dict)
  - Create `tests/test_models.py` — verify models serialize/deserialize correctly (JSON round-trip)
  - All models must have `.to_json()` / `.from_json()` support (via Pydantic)

  **Must NOT do**:
  - No simulation logic
  - No Streamlit imports
  - No file I/O (just data structures)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Pydantic model definitions, straightforward
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3, 4, 5, 6)
  - **Blocks**: Tasks 7, 8, 9, 12
  - **Blocked By**: Task 1 (needs project structure)

  **References**:

  **Pattern References**:
  - `Revamp Master Doc.jpg` — All game mechanics and data structures visible in flowchart

  **External References**:
  - Pydantic v2 docs: https://docs.pydantic.dev/latest/ — Model definition, serialization, validation

  **WHY Each Reference Matters**:
  - The Revamp Master Doc defines what state the simulation must track (levels, streaks, progression scores)
  - Pydantic provides JSON serialization needed for URL config sharing

  **Acceptance Criteria**:

  - [ ] `pytest tests/test_models.py -v` → PASS

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Models serialize/deserialize correctly
    Tool: Bash (pytest)
    Preconditions: requirements.txt installed
    Steps:
      1. Run: pytest tests/test_models.py -v
      2. Assert: all tests pass
      3. Verify: Card model creates with default level=1
      4. Verify: SimConfig serializes to JSON and deserializes back identically
    Expected Result: All model tests pass, JSON round-trip is lossless
    Failure Indicators: ValidationError, JSON decode error, field mismatch
    Evidence: .sisyphus/evidence/task-2-model-tests.txt

  Scenario: No Streamlit imports in simulation package
    Tool: Bash (grep)
    Preconditions: simulation/models.py exists
    Steps:
      1. Run: grep -r "import streamlit" simulation/
      2. Assert: no matches found (exit code 1)
    Expected Result: Zero Streamlit imports in simulation/
    Failure Indicators: Any match found
    Evidence: .sisyphus/evidence/task-2-no-streamlit.txt
  ```

  **Commit**: YES (group with Task 3)
  - Message: `feat(models): add data models and default config fixtures`
  - Files: `simulation/models.py, tests/test_models.py`
  - Pre-commit: `pytest tests/test_models.py -v`

- [x] 3. Default Data JSON Fixtures

  **What to do**:
  - Create `data/defaults/` directory with JSON files for ALL configurable tables:
    - `pack_configs.json` — 9 pack types, each with name and placeholder card_types_table (total_unlocked → card_types_yielded). Use reasonable placeholder values (e.g., {31: 3, 40: 4, 50: 5} for each pack). Structure must match PackConfig model.
    - `upgrade_tables.json` — 3 entries (Gold Shared, Blue Shared, Unique). Each has: duplicate_costs (99 entries for shared, 9 for unique), coin_costs (same), bluestar_rewards (same). Use escalating placeholder values.
    - `duplicate_ranges.json` — 3 entries. Each has min_pct and max_pct arrays per level. Placeholder: [0.05, 0.15] for all levels.
    - `coin_per_duplicate.json` — 3 entries. Coins earned per duplicate at each level. Placeholder: escalating from 1.
    - `progression_mapping.json` — The Shared↔Unique level mapping table from the Revamp Master Doc: {1:1, 5:2, 10:3, 15:4, 25:5, 45:6, 60:7, 70:8, 80:9, 90:10, 100:10} (Note: unique max is 10, so shared 100 maps to unique 10, not 11).
    - `unique_unlock_schedule.json` — Day-by-day unique card unlock count. Placeholder: {1: 8, 30: 1, 60: 1, 90: 1} (start with 8, add 1 every 30 days).
    - `pack_averages.json` — 20-day average packs per day for each of 9 pack types. Placeholder: all 1.0.
  - Create `simulation/config_loader.py` — function `load_defaults() → SimConfig` that reads all JSON files and constructs a SimConfig
  - Create `tests/test_config_loader.py` — verify load_defaults returns valid SimConfig

  **Must NOT do**:
  - No real game data yet (user will provide later — these are placeholders)
  - No Streamlit imports
  - Don't hardcode paths (use relative paths from project root or config)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: JSON file creation + simple loader function
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 4, 5, 6)
  - **Blocks**: Task 12 (config editor needs defaults)
  - **Blocked By**: Task 1 (needs project structure)

  **References**:

  **Pattern References**:
  - `Revamp Master Doc.jpg` — Progression mapping table visible in top-right corner
  - `simulation/models.py` (from Task 2) — JSON structure must match Pydantic model schemas

  **Acceptance Criteria**:

  - [ ] `pytest tests/test_config_loader.py -v` → PASS

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Default config loads successfully
    Tool: Bash (pytest)
    Preconditions: Task 2 models completed
    Steps:
      1. Run: pytest tests/test_config_loader.py -v
      2. Assert: load_defaults() returns a valid SimConfig
      3. Assert: SimConfig has exactly 9 pack configs
      4. Assert: progression_mapping contains {1:1, 5:2, ..., 100:10}
    Expected Result: All config loader tests pass
    Failure Indicators: FileNotFoundError, ValidationError, wrong pack count
    Evidence: .sisyphus/evidence/task-3-config-loader.txt

  Scenario: JSON files are valid and parseable
    Tool: Bash (python)
    Preconditions: data/defaults/*.json files exist
    Steps:
      1. Run: python -c "import json, glob; [json.load(open(f)) for f in glob.glob('data/defaults/*.json')]; print('All JSON valid')"
      2. Assert: "All JSON valid" printed, no errors
    Expected Result: All JSON files parse without errors
    Failure Indicators: json.JSONDecodeError
    Evidence: .sisyphus/evidence/task-3-json-valid.txt
  ```

  **Commit**: YES (group with Task 2)
  - Message: `feat(models): add data models and default config fixtures`
  - Files: `data/defaults/*.json, simulation/config_loader.py, tests/test_config_loader.py`
  - Pre-commit: `pytest tests/test_config_loader.py -v`

- [x] 4. Pack System Module

  **What to do**:
  - Create `simulation/pack_system.py`:
    - `process_packs_for_day(game_state: GameState, config: SimConfig, rng: Random | None) → list[CardPull]`
      - For each pack type, compute how many packs opened today using `pack_averages[pack_name]`:
        - Deterministic: `round(daily_avg)` packs (or fractional accumulation)
        - MC: `Poisson(daily_avg)` or similar stochastic count
      - For each pack opened:
        - Look up `card_types_table[total_unlocked_cards]` → number of card types yielded this pack
        - Return a list of `CardPull` objects (each = one card type to feed into the drop algorithm)
    - `CardPull` dataclass: pack_name (str), pull_index (int)
    - Handle edge case: if `total_unlocked_cards` key not in table, use closest lower key (floor lookup)
  - Create `tests/test_pack_system.py`:
    - Test: 0 packs/day yields 0 pulls
    - Test: deterministic mode with avg=2.5 → 2 or 3 packs (consistent rounding)
    - Test: floor lookup when exact key missing
    - Test: correct total pulls across multiple pack types

  **Must NOT do**:
  - No card selection logic (that's the drop algorithm, Task 7-8)
  - No coin calculations (Task 6)
  - No Streamlit imports

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple lookup table logic with straightforward tests
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `playwright`: No browser work needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3, 5, 6)
  - **Blocks**: Task 10 (orchestrator needs pack processing)
  - **Blocked By**: Task 1 (needs project structure)

  **References**:

  **Pattern References**:
  - `simulation/models.py` (Task 2) — `PackConfig.card_types_table`, `GameState.cards` for total_unlocked count
  - `data/defaults/pack_configs.json` (Task 3) — Pack table structure
  - `data/defaults/pack_averages.json` (Task 3) — Daily average values

  **API/Type References**:
  - `simulation/models.py:PackConfig` — `card_types_table: dict[int, int]` mapping
  - `simulation/models.py:SimConfig` — `pack_averages: dict[str, float]`

  **WHY Each Reference Matters**:
  - `PackConfig.card_types_table` defines the lookup that maps unlocked count → card types yielded per pack
  - `pack_averages` provides the daily rate input (user's 20-day average per pack type)

  **Acceptance Criteria**:

  - [ ] `pytest tests/test_pack_system.py -v` → PASS

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Correct pull count for known input
    Tool: Bash (pytest)
    Preconditions: Models (Task 2) available
    Steps:
      1. Create a SimConfig with 2 pack types: PackA (avg=3.0, table={0:1, 10:2, 20:3}), PackB (avg=1.0, table={0:1})
      2. Create GameState with 15 unlocked cards
      3. Call process_packs_for_day in deterministic mode
      4. Assert: PackA yields 3 packs × 2 card types each = 6 pulls (floor lookup: 15 → key 10 → 2 types)
      5. Assert: PackB yields 1 pack × 1 card type = 1 pull
      6. Assert: total = 7 CardPull objects
    Expected Result: 7 CardPull objects with correct pack_name attribution
    Failure Indicators: Wrong pull count, KeyError on table lookup
    Evidence: .sisyphus/evidence/task-4-pack-pulls.txt

  Scenario: Zero packs yields zero pulls
    Tool: Bash (pytest)
    Preconditions: Models available
    Steps:
      1. Create SimConfig with pack_averages all set to 0.0
      2. Call process_packs_for_day
      3. Assert: returns empty list
    Expected Result: Empty list, no errors
    Failure Indicators: Non-empty result, division by zero
    Evidence: .sisyphus/evidence/task-4-zero-packs.txt
  ```

  **Commit**: YES (group with Tasks 5, 6)
  - Message: `feat(core): add pack system, progression mapping, and coin economy`
  - Files: `simulation/pack_system.py, tests/test_pack_system.py`
  - Pre-commit: `pytest tests/test_pack_system.py -v`

- [x] 5. Progression Mapping + Gating Logic

  **What to do**:
  - Create `simulation/progression.py`:
    - `get_max_unique_level(avg_shared_level: float, mapping: ProgressionMapping) → int`
      - Given average shared card level, look up the maximum unique level allowed
      - Floor lookup: find highest shared_level entry ≤ avg_shared_level, return corresponding unique_level
      - Example: avg_shared=12 → shared_levels [1,5,10,15,...] → floor to 10 → unique level 3
    - `compute_progression_score(card: Card, mapping: ProgressionMapping) → float`
      - Normalize card level to a 0-1 scale using the mapping table
      - For shared cards: `level / max_shared_level` (100)
      - For unique cards: `level / max_unique_level` (10)
    - `compute_category_progression(cards: list[Card], category: CardCategory, mapping: ProgressionMapping) → float`
      - Average progression score across all cards in a category
    - `can_upgrade_unique(card: Card, avg_shared_level: float, mapping: ProgressionMapping) → bool`
      - Check if upgrading this unique card would exceed the gated max unique level
    - `get_unlocked_unique_count(day: int, schedule: dict[int, int]) → int`
      - Given current day and unlock schedule, return total unique cards unlocked
      - Sum all schedule entries where day_key ≤ current day
  - Create `tests/test_progression.py`:
    - Test: gating at exact boundary (shared=10 → unique max=3, so unique level 3 OK, level 4 blocked)
    - Test: gating between boundaries (shared=12 → still max=3)
    - Test: progression score normalization (shared level 50/100 = 0.5, unique level 5/10 = 0.5)
    - Test: unlock schedule accumulation (day 35 with schedule {1:8, 30:1} → 9 unique cards)

  **Must NOT do**:
  - No drop algorithm logic
  - No upgrade execution (just gating check)
  - No Streamlit imports

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Pure math functions with table lookups, straightforward
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3, 4, 6)
  - **Blocks**: Tasks 7, 9 (drop algorithm and upgrade engine need gating)
  - **Blocked By**: Task 1 (needs project structure)

  **References**:

  **Pattern References**:
  - `simulation/models.py` (Task 2) — `ProgressionMapping`, `Card`, `CardCategory`
  - `data/defaults/progression_mapping.json` (Task 3) — Default mapping: {1:1, 5:2, 10:3, 15:4, 25:5, 45:6, 60:7, 70:8, 80:9, 90:10, 100:10}
  - `data/defaults/unique_unlock_schedule.json` (Task 3) — Default unlock schedule

  **WHY Each Reference Matters**:
  - The mapping table is the core lookup for both gating and progression score computation
  - Progression scores feed directly into the drop algorithm's Gap calculation (Task 7)
  - Gating check prevents unique cards from leveling past what shared progression allows

  **Acceptance Criteria**:

  - [ ] `pytest tests/test_progression.py -v` → PASS

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Gating correctly blocks over-leveled unique
    Tool: Bash (pytest)
    Preconditions: Models available with default progression mapping
    Steps:
      1. Set avg_shared_level = 12
      2. Call get_max_unique_level(12, default_mapping)
      3. Assert: returns 3 (floor lookup: 10 → 3)
      4. Call can_upgrade_unique(card_at_level_3, 12, mapping)
      5. Assert: returns False (already at max)
      6. Call can_upgrade_unique(card_at_level_2, 12, mapping)
      7. Assert: returns True (level 2 → 3 is allowed)
    Expected Result: Gating correctly allows/blocks based on mapping
    Failure Indicators: Unique card upgrades past allowed level
    Evidence: .sisyphus/evidence/task-5-gating.txt

  Scenario: Progression score normalization is correct
    Tool: Bash (pytest)
    Preconditions: Models available
    Steps:
      1. Create shared card at level 50 (max 100)
      2. Create unique card at level 5 (max 10)
      3. Compute progression scores for both
      4. Assert: both return 0.5
    Expected Result: Scores correctly normalized to 0-1 range
    Failure Indicators: Score outside [0,1], wrong normalization base
    Evidence: .sisyphus/evidence/task-5-scores.txt
  ```

  **Commit**: YES (group with Tasks 4, 6)
  - Message: `feat(core): add pack system, progression mapping, and coin economy`
  - Files: `simulation/progression.py, tests/test_progression.py`
  - Pre-commit: `pytest tests/test_progression.py -v`

- [x] 6. Coin Economy Module

  **What to do**:
  - Create `simulation/coin_economy.py`:
    - `compute_coin_income(card: Card, duplicates_received: int, config: SimConfig) → int`
      - Look up `coin_per_duplicate[card.category][card.level]` → coins per dupe
      - Return `duplicates_received * coins_per_dupe`
    - `compute_upgrade_coin_cost(card: Card, config: SimConfig) → int`
      - Look up `upgrade_tables[card.category].coin_costs[card.level - 1]` (0-indexed array)
      - Return the coin cost for upgrading from current level to next
    - `can_afford_upgrade(coins: int, card: Card, config: SimConfig) → bool`
      - Check if current coin balance ≥ upgrade cost
    - `CoinTransaction` dataclass: amount (int), source (str — "pack_income" | "upgrade_spend"), card_id (str), day (int)
    - `CoinLedger` class:
      - `balance: int`
      - `transactions: list[CoinTransaction]` (for daily tracking)
      - `add_income(amount, card_id, day)`
      - `spend(amount, card_id, day) → bool` (returns False if insufficient)
      - `daily_summary(day) → dict` with total_income, total_spent, balance
    - Handle maxed cards: when a card is at max level and pulled, award flat coin reward (configurable per category). No duplicates awarded.
  - Create `tests/test_coin_economy.py`:
    - Test: income calculation at various levels
    - Test: spend fails when balance insufficient
    - Test: daily summary aggregation
    - Test: maxed card flat reward

  **Must NOT do**:
  - No upgrade execution (just coin tracking)
  - No Streamlit imports
  - No persistent storage (in-memory ledger only)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Straightforward accounting logic with table lookups
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3, 4, 5)
  - **Blocks**: Task 9 (upgrade engine needs coin checks)
  - **Blocked By**: Task 1 (needs project structure)

  **References**:

  **Pattern References**:
  - `simulation/models.py` (Task 2) — `CoinPerDuplicate`, `UpgradeTable.coin_costs`, `Card`, `CardCategory`
  - `data/defaults/coin_per_duplicate.json` (Task 3) — Default coins-per-dupe tables
  - `data/defaults/upgrade_tables.json` (Task 3) — Coin cost columns

  **WHY Each Reference Matters**:
  - `CoinPerDuplicate` lookup determines income per card pull — the ONLY coin source in the system
  - `UpgradeTable.coin_costs` determines spend per upgrade — coins can bottleneck entire progression
  - The CoinLedger provides the daily income/spend breakdown needed for the coin flow chart (Task 15)

  **Acceptance Criteria**:

  - [ ] `pytest tests/test_coin_economy.py -v` → PASS

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Coin income matches lookup table
    Tool: Bash (pytest)
    Preconditions: Models available
    Steps:
      1. Create Gold Shared card at level 5
      2. Set coin_per_duplicate for Gold Shared level 5 = 10
      3. Call compute_coin_income(card, duplicates_received=8)
      4. Assert: returns 80 (8 × 10)
    Expected Result: 80 coins
    Failure Indicators: Wrong multiplication, index off-by-one
    Evidence: .sisyphus/evidence/task-6-income.txt

  Scenario: Spend fails on insufficient balance
    Tool: Bash (pytest)
    Preconditions: CoinLedger initialized
    Steps:
      1. Create CoinLedger with balance=0
      2. Call spend(amount=100, card_id="gold_1", day=1)
      3. Assert: returns False
      4. Assert: balance still 0
      5. Add income of 50
      6. Call spend(amount=100)
      7. Assert: returns False, balance still 50
      8. Call spend(amount=30)
      9. Assert: returns True, balance now 20
    Expected Result: Spend correctly rejects when balance insufficient
    Failure Indicators: Negative balance, spend succeeds with insufficient funds
    Evidence: .sisyphus/evidence/task-6-spend-fail.txt
  ```

  **Commit**: YES (group with Tasks 4, 5)
  - Message: `feat(core): add pack system, progression mapping, and coin economy`
  - Files: `simulation/coin_economy.py, tests/test_coin_economy.py`
  - Pre-commit: `pytest tests/test_coin_economy.py -v`

- [x] 7. Card Drop Algorithm — Phase 1: Rarity Decision

  **What to do**:
  - Create `simulation/drop_algorithm.py`:
    - `decide_rarity(game_state: GameState, config: SimConfig, rng: Random | None) → CardCategory`
      - Implements the EXACT Revamp Master Doc Phase 1 algorithm:
      1. Compute progression scores:
         - `SShared = compute_category_progression(shared_cards, SHARED, mapping)` (average across Gold+Blue)
         - `SUnique = compute_category_progression(unique_cards, UNIQUE, mapping)`
      2. Gap-based weight adjustment:
         - `Gap = SUnique - SShared`
         - `WShared = config.base_shared_rate * (1.5 ** Gap)`
         - `WUnique = config.base_unique_rate * (1.5 ** (-Gap))`
      3. Streak penalty:
         - `FinalWeightShared = WShared * (0.6 ** game_state.streak_state.streak_shared)`
         - `FinalWeightUnique = WUnique * (0.3 ** game_state.streak_state.streak_unique)`
      4. Normalize:
         - `Total = FinalWeightShared + FinalWeightUnique`
         - `ProbShared = FinalWeightShared / Total`
         - `ProbUnique = FinalWeightUnique / Total`
      5. Roll:
         - Deterministic (rng=None): return SHARED if ProbShared ≥ 0.5, else UNIQUE
         - MC (rng provided): `rng.random() < ProbShared` → SHARED, else UNIQUE
    - `update_rarity_streak(streak_state: StreakState, chosen: CardCategory) → StreakState`
      - If SHARED chosen: streak_shared += 1, streak_unique = 0
      - If UNIQUE chosen: streak_unique += 1, streak_shared = 0
    - Export constants: `STREAK_DECAY_SHARED = 0.6`, `STREAK_DECAY_UNIQUE = 0.3`, `GAP_BASE = 1.5`
  - Create `tests/test_drop_algorithm.py`:
    - Test: balanced state (SShared=SUnique, no streaks) → probabilities close to 70/30
    - Test: large positive Gap (unique ahead) → shared probability increases
    - Test: large negative Gap (shared ahead) → unique probability increases
    - Test: streak of 3 shared → shared weight heavily penalized
    - Test: streak update logic (reset counter on switch)
    - Test: deterministic mode returns majority category
    - Test: statistical test — 10,000 MC rolls at balanced state → shared between 67-73% (within 3%)

  **Must NOT do**:
  - No card SELECTION within category (that's Phase 2, Task 8)
  - No pack processing
  - No upgrade logic
  - No Streamlit imports
  - Do NOT hardcode base rates — use config values

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Critical algorithm with precise mathematical formulas, needs careful implementation matching Revamp Master Doc exactly
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `playwright`: No browser work

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 8, 9)
  - **Blocks**: Task 8 (Phase 2 depends on Phase 1 output), Task 10 (orchestrator)
  - **Blocked By**: Task 2 (models), Task 5 (progression scores)

  **References**:

  **Pattern References**:
  - `Revamp Master Doc.jpg` — **CRITICAL**: The exact flowchart for Phase 1 rarity decision. This is the AUTHORITATIVE source. The agent MUST study this image and implement EXACTLY what it shows.
  - `simulation/progression.py` (Task 5) — `compute_category_progression()` provides SShared and SUnique values

  **API/Type References**:
  - `simulation/models.py:StreakState` — streak_shared, streak_unique counters
  - `simulation/models.py:GameState` — cards list, streak_state
  - `simulation/models.py:SimConfig` — base_shared_rate, base_unique_rate

  **WHY Each Reference Matters**:
  - The Revamp Master Doc is the SOLE authority on the algorithm — any deviation is a bug
  - `compute_category_progression()` from Task 5 is the exact function that computes SShared/SUnique
  - StreakState tracks consecutive same-type pulls for the streak penalty formula

  **Acceptance Criteria**:

  - [ ] `pytest tests/test_drop_algorithm.py -v` → PASS

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Balanced state produces ~70/30 split
    Tool: Bash (pytest)
    Preconditions: All shared cards at level 50/100, all unique at level 5/10 (equal progression)
    Steps:
      1. Create GameState with equal progression, zero streaks
      2. Run decide_rarity 10,000 times with seeded RNG
      3. Count shared vs unique decisions
      4. Assert: shared ratio between 0.67 and 0.73
    Expected Result: ~70% shared, ~30% unique
    Failure Indicators: Ratio outside [0.67, 0.73], crash on divide-by-zero
    Evidence: .sisyphus/evidence/task-7-balanced-rates.txt

  Scenario: Gap adjustment shifts probabilities correctly
    Tool: Bash (pytest)
    Preconditions: Models available
    Steps:
      1. Create state where SUnique=0.8, SShared=0.2 (Gap=0.6, unique way ahead)
      2. Compute rarity probabilities (no streak)
      3. Assert: ProbShared > 0.75 (system tries to catch up shared)
      4. Create opposite: SShared=0.8, SUnique=0.2 (Gap=-0.6)
      5. Assert: ProbUnique > 0.35 (system tries to catch up unique)
    Expected Result: Gap correctly shifts weights toward lagging category
    Failure Indicators: Gap applied in wrong direction, probabilities don't sum to 1.0
    Evidence: .sisyphus/evidence/task-7-gap-adjustment.txt

  Scenario: Streak penalty reduces repeated category probability
    Tool: Bash (pytest)
    Preconditions: Balanced progression state
    Steps:
      1. Set streak_shared=3, streak_unique=0
      2. Compute rarity probabilities
      3. Assert: ProbShared < 0.40 (heavily penalized: 0.7 * 0.6^3 = 0.1512)
      4. Set streak_unique=3, streak_shared=0
      5. Assert: ProbUnique < 0.05 (even more penalized: 0.3 * 0.3^3 = 0.0081)
    Expected Result: Streaks dramatically reduce repeated category probability
    Failure Indicators: Streak has no effect, wrong decay constant
    Evidence: .sisyphus/evidence/task-7-streak-penalty.txt
  ```

  **Commit**: YES (group with Task 8)
  - Message: `feat(drop): implement full card drop algorithm from Revamp Master Doc`
  - Files: `simulation/drop_algorithm.py, tests/test_drop_algorithm.py`
  - Pre-commit: `pytest tests/test_drop_algorithm.py -v`

- [x] 8. Card Drop Algorithm — Phase 2: Card Selection

  **What to do**:
  - Add to `simulation/drop_algorithm.py` (same file as Task 7):
    - `select_shared_card(game_state: GameState, config: SimConfig, rng: Random | None) → Card`
      - Phase 2a from Revamp Master Doc:
      1. Get ALL shared cards (Gold + Blue) sorted by level ascending
      2. Take top N lowest level cards (N = total shared cards, since 23 < original 33 threshold)
      3. For each candidate card:
         - `WeightCard = 1 / (card.level + 1)`
         - Determine color streak (Gold vs Blue): look at `streak_state.streak_per_color[card.category_sub]`
         - `FinalWeightCard = WeightCard * (0.6 ** streak_for_this_color)`
      4. Weighted selection among candidates:
         - Deterministic: pick card with highest FinalWeightCard
         - MC: weighted random choice using FinalWeightCard as weights
    - `select_unique_card(game_state: GameState, config: SimConfig, rng: Random | None) → Card`
      - Phase 2b from Revamp Master Doc:
      1. Get all UNLOCKED unique cards sorted by level ascending
      2. Take top 10 lowest level (or all if fewer than 10)
      3. For each candidate card:
         - `WeightCard = 1 / (card.level + 1)`
         - Look up hero streak: `streak_state.streak_per_hero[card.id]`
         - `FinalWeightCard = WeightCard * (0.6 ** streak_for_this_hero)`
      4. Weighted selection (same as shared)
    - `update_card_streak(streak_state: StreakState, selected_card: Card) → StreakState`
      - For shared: increment streak for selected color (GOLD or BLUE), reset other color streak
      - For unique: increment streak for selected hero, reset all other hero streaks
    - `compute_duplicates_received(card: Card, config: SimConfig, rng: Random | None) → int`
      - Look up `duplicate_ranges[card.category]` for current level
      - Get `min_pct` and `max_pct` for this level
      - Look up `upgrade_tables[card.category].duplicate_costs[card.level - 1]` as the base
      - Deterministic: `round(base * (min_pct + max_pct) / 2)`
      - MC: `round(base * rng.uniform(min_pct, max_pct))`
      - Handle MAXED cards: if card at max level, return 0 duplicates (flat coin reward handled by coin economy)
    - `perform_card_pull(game_state: GameState, config: SimConfig, rng: Random | None) → tuple[Card, int, int]`
      - Orchestrates one full pull: Phase 1 → Phase 2 → compute duplicates → update streaks
      - Returns: (selected_card, duplicates_received, coin_income)
  - Add to `tests/test_drop_algorithm.py`:
    - Test: lowest level cards get highest weight
    - Test: color streak penalizes repeated color
    - Test: hero streak penalizes repeated hero
    - Test: deterministic picks highest-weighted card
    - Test: maxed card returns 0 duplicates
    - Test: duplicate range midpoint calculation
    - Test: full pull integration (Phase 1 → Phase 2 → duplicates)

  **Must NOT do**:
  - No upgrade execution
  - No pack processing
  - No Streamlit imports
  - Do NOT modify Phase 1 logic from Task 7

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Complex weighted selection with streak tracking, requires careful integration with Phase 1
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Task 7)
  - **Parallel Group**: Wave 2 (AFTER Task 7 completes)
  - **Blocks**: Task 10 (orchestrator)
  - **Blocked By**: Task 2 (models), Task 7 (Phase 1 must exist first)

  **References**:

  **Pattern References**:
  - `Revamp Master Doc.jpg` — **CRITICAL**: Phase 2a (shared card selection) and Phase 2b (unique card selection) flowchart sections
  - `simulation/drop_algorithm.py` (Task 7) — Phase 1 `decide_rarity()` output feeds into Phase 2

  **API/Type References**:
  - `simulation/models.py:StreakState` — `streak_per_color: dict[str, int]`, `streak_per_hero: dict[str, int]`
  - `simulation/models.py:DuplicateRange` — `min_pct`, `max_pct` arrays per level
  - `simulation/models.py:UpgradeTable` — `duplicate_costs` for base value in dupe calculation

  **WHY Each Reference Matters**:
  - The Revamp Master Doc defines Phase 2a/2b exactly — must match
  - `streak_per_color` and `streak_per_hero` drive the anti-repeat penalty in card selection
  - `DuplicateRange` determines how many duplicates each pull yields — the fundamental resource generation

  **Acceptance Criteria**:

  - [ ] `pytest tests/test_drop_algorithm.py -v` → PASS (all tests including Phase 1 from Task 7)

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Lower level cards selected more often
    Tool: Bash (pytest)
    Preconditions: 5 shared cards at levels [1, 5, 10, 20, 50]
    Steps:
      1. Run select_shared_card 1000 times with seeded RNG, zero streaks
      2. Count selections per card
      3. Assert: level-1 card selected most often (weight = 1/2 = 0.5)
      4. Assert: level-50 card selected least often (weight = 1/51 ≈ 0.02)
    Expected Result: Selection frequency inversely proportional to (level+1)
    Failure Indicators: Uniform distribution, wrong weighting direction
    Evidence: .sisyphus/evidence/task-8-level-weighting.txt

  Scenario: Maxed card yields 0 duplicates
    Tool: Bash (pytest)
    Preconditions: Card at max level (100 for shared, 10 for unique)
    Steps:
      1. Create Gold Shared card at level 100
      2. Call compute_duplicates_received(maxed_card, config, rng=None)
      3. Assert: returns 0
    Expected Result: Zero duplicates for maxed card
    Failure Indicators: Non-zero return, index out of bounds
    Evidence: .sisyphus/evidence/task-8-maxed-card.txt

  Scenario: Full pull integration produces valid output
    Tool: Bash (pytest)
    Preconditions: Complete GameState with mixed-level cards
    Steps:
      1. Create GameState with 23 shared cards (levels 1-23) and 8 unique cards (levels 1-3)
      2. Call perform_card_pull(game_state, config, rng=seeded)
      3. Assert: returns (Card, int ≥ 0, int ≥ 0)
      4. Assert: selected card exists in game_state.cards
      5. Assert: streak_state updated correctly
    Expected Result: Valid card selected with non-negative duplicates and coin income
    Failure Indicators: Card not in state, negative values, streak not updated
    Evidence: .sisyphus/evidence/task-8-full-pull.txt
  ```

  **Commit**: YES (group with Task 7)
  - Message: `feat(drop): implement full card drop algorithm from Revamp Master Doc`
  - Files: `simulation/drop_algorithm.py, tests/test_drop_algorithm.py`
  - Pre-commit: `pytest tests/test_drop_algorithm.py -v`

- [x] 9. Upgrade Engine

  **What to do**:
  - Create `simulation/upgrade_engine.py`:
    - `attempt_upgrades(game_state: GameState, config: SimConfig, coin_ledger: CoinLedger) → list[UpgradeEvent]`
      - Greedy auto-upgrade with priority: Unique > Gold Shared > Blue Shared
      - Within a category, upgrade the LOWEST level card first (catch-up)
      - For each candidate card:
        1. Check duplicate requirement: `card.duplicates >= upgrade_tables[card.category].duplicate_costs[card.level - 1]`
        2. Check coin requirement: `coin_ledger.balance >= upgrade_tables[card.category].coin_costs[card.level - 1]`
        3. Check gating (unique only): `can_upgrade_unique(card, avg_shared_level, mapping)`
        4. Check max level: `card.level < max_level` (100 for shared, 10 for unique)
        5. If ALL pass: execute upgrade
      - Execute upgrade:
        - `card.level += 1`
        - `card.duplicates -= duplicate_cost`
        - `coin_ledger.spend(coin_cost, card.id, day)`
        - Compute bluestar reward: `upgrade_tables[card.category].bluestar_rewards[card.level - 2]` (reward for reaching new level)
        - `game_state.total_bluestars += bluestar_reward`
      - **Loop until no more upgrades possible** (multiple upgrades per day)
      - Return list of UpgradeEvent(card_id, old_level, new_level, dupes_spent, coins_spent, bluestars_earned)
    - `UpgradeEvent` dataclass: card_id, old_level, new_level, dupes_spent, coins_spent, bluestars_earned, day
    - `get_upgrade_candidates(game_state: GameState, config: SimConfig) → list[Card]`
      - Returns cards sorted by priority: all Unique (sorted by level asc), then Gold (level asc), then Blue (level asc)
  - Create `tests/test_upgrade_engine.py`:
    - Test: upgrade happens when dupes AND coins sufficient
    - Test: upgrade blocked when dupes insufficient
    - Test: upgrade blocked when coins insufficient
    - Test: upgrade blocked by gating (unique card can't pass shared level)
    - Test: priority order: unique card upgrades before gold, gold before blue
    - Test: multiple upgrades in one day (loop continues until blocked)
    - Test: bluestar reward correctly added to total
    - Test: maxed card not eligible for upgrade
    - Test: within-category ordering (lowest level first)

  **Must NOT do**:
  - No pack or drop logic
  - No Streamlit imports
  - Do NOT implement alternative strategies (greedy ONLY)
  - Do NOT allow upgrade when card is at max level

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Complex interplay of 4 conditions (dupes, coins, gating, max), priority ordering, and multi-upgrade loops
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 7, 8 — but can start as soon as Tasks 2, 5, 6 complete)
  - **Blocks**: Task 10 (orchestrator needs upgrade engine)
  - **Blocked By**: Task 2 (models), Task 5 (gating), Task 6 (coin economy)

  **References**:

  **Pattern References**:
  - `simulation/progression.py` (Task 5) — `can_upgrade_unique()` for gating check
  - `simulation/coin_economy.py` (Task 6) — `CoinLedger.spend()` for coin deduction, `can_afford_upgrade()`

  **API/Type References**:
  - `simulation/models.py:UpgradeTable` — `duplicate_costs`, `coin_costs`, `bluestar_rewards` arrays
  - `simulation/models.py:Card` — `level`, `duplicates`, `category`
  - `simulation/models.py:GameState` — `total_bluestars`

  **WHY Each Reference Matters**:
  - `can_upgrade_unique()` is the gating check that prevents unique cards from outpacing shared progression
  - `CoinLedger` tracks the shared coin pool — upgrades compete for the same coins
  - The priority ordering (Unique > Gold > Blue) determines which cards get coins first when pool is limited

  **Acceptance Criteria**:

  - [ ] `pytest tests/test_upgrade_engine.py -v` → PASS

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Upgrade executes correctly when all conditions met
    Tool: Bash (pytest)
    Preconditions: Card with 100 dupes, 500 coins, upgrade cost = 50 dupes + 200 coins, not gated
    Steps:
      1. Create Gold Shared card at level 5 with 100 duplicates
      2. Create CoinLedger with balance=500
      3. Set upgrade cost: 50 dupes, 200 coins for level 5→6
      4. Set bluestar reward for reaching level 6 = 10
      5. Call attempt_upgrades
      6. Assert: card.level = 6
      7. Assert: card.duplicates = 50 (100 - 50)
      8. Assert: coin_ledger.balance = 300 (500 - 200)
      9. Assert: game_state.total_bluestars increased by 10
    Expected Result: Upgrade succeeds, resources correctly deducted, bluestars awarded
    Failure Indicators: Resources not deducted, bluestar not added, level unchanged
    Evidence: .sisyphus/evidence/task-9-upgrade-success.txt

  Scenario: Priority order respected when coins limited
    Tool: Bash (pytest)
    Preconditions: One unique, one gold, one blue card — all have enough dupes. Coins only for 1 upgrade.
    Steps:
      1. Create 3 cards: Unique (level 2, 50 dupes), Gold (level 5, 100 dupes), Blue (level 5, 100 dupes)
      2. Set coin costs: 100 for each upgrade
      3. Create CoinLedger with balance=100 (only 1 upgrade affordable)
      4. Call attempt_upgrades
      5. Assert: Unique card upgraded (level 3)
      6. Assert: Gold and Blue NOT upgraded (coins exhausted)
    Expected Result: Unique gets priority over Gold/Blue
    Failure Indicators: Gold or Blue upgraded instead of Unique
    Evidence: .sisyphus/evidence/task-9-priority.txt

  Scenario: Gating prevents unique from over-leveling
    Tool: Bash (pytest)
    Preconditions: Unique card at level 3 with plenty of dupes+coins, but avg shared level = 12 (max unique = 3)
    Steps:
      1. Create Unique card at level 3, 999 dupes
      2. CoinLedger balance = 99999
      3. Avg shared level = 12 (maps to max unique = 3)
      4. Call attempt_upgrades
      5. Assert: Unique card NOT upgraded (already at gated max)
      6. Assert: no UpgradeEvent for this card
    Expected Result: Gating blocks the upgrade despite having resources
    Failure Indicators: Unique card upgrades past gated level
    Evidence: .sisyphus/evidence/task-9-gating-block.txt
  ```

  **Commit**: YES
  - Message: `feat(upgrade): add upgrade engine with gating and coin management`
  - Files: `simulation/upgrade_engine.py, tests/test_upgrade_engine.py`
  - Pre-commit: `pytest tests/test_upgrade_engine.py -v`

- [x] 10. Simulation Orchestrator — Deterministic Mode

  **What to do**:
  - Create `simulation/orchestrator.py`:
    - `DailySnapshot` dataclass: day (int), total_bluestars (int), bluestars_earned_today (int), coins_balance (int), coins_earned_today (int), coins_spent_today (int), card_levels (dict[str, int]) — card_id→level, upgrades_today (list[UpgradeEvent]), category_avg_levels (dict[str, float]) — category→avg_level, total_unique_unlocked (int)
    - `run_simulation(config: SimConfig, rng: Random | None = None) → SimResult`
      - Main deterministic simulation loop (rng=None for deterministic):
      1. Initialize GameState:
         - Create all cards: 9 Gold Shared + 14 Blue Shared + initial unique cards (from unlock schedule day 1)
         - All cards start at level 1, 0 duplicates
         - Initialize StreakState with all zeros
         - Initialize CoinLedger with balance=0
      2. For each day (1 to config.num_days):
         a. Check unique unlock schedule: if new cards unlock today, add them (level 1, 0 dupes)
         b. Process packs: `process_packs_for_day(game_state, config, rng)` → list of CardPull
         c. For each CardPull:
            - `perform_card_pull(game_state, config, rng)` → (card, dupes, coins)
            - Add duplicates to card: `card.duplicates += dupes`
            - Add coin income: `coin_ledger.add_income(coins, card.id, day)`
         d. Attempt upgrades: `attempt_upgrades(game_state, config, coin_ledger)` → upgrade_events
         e. Record DailySnapshot
      3. Return SimResult with all snapshots + summary totals
    - `create_initial_state(config: SimConfig) → tuple[GameState, CoinLedger]`
      - Separate initialization for testability
    - Keep file under 200 lines — delegate to sub-modules
  - Create `tests/test_orchestrator.py`:
    - Test: 1-day deterministic simulation produces valid snapshot
    - Test: card duplicates accumulate across days
    - Test: upgrades fire when threshold crossed
    - Test: unique unlock schedule adds cards on correct day
    - Test: total bluestars = sum of all upgrade rewards
    - Test: coin balance = income - spending
    - Test: 100-day simulation completes in < 30 seconds (performance)

  **Must NOT do**:
  - No Monte Carlo logic (that's Task 11)
  - No Streamlit imports
  - No chart rendering
  - File must NOT exceed 300 lines

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Central integration module wiring together 5 sub-modules — needs careful state management and correct ordering
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (can run in parallel with Task 11 ONLY after Task 10 skeleton exists — but practically Task 11 depends on Task 10)
  - **Blocks**: Task 11, 13, 14, 15, 16 (everything downstream)
  - **Blocked By**: Tasks 4, 7, 8, 9 (all engine modules)

  **References**:

  **Pattern References**:
  - `simulation/pack_system.py` (Task 4) — `process_packs_for_day()` — first step in daily loop
  - `simulation/drop_algorithm.py` (Tasks 7-8) — `perform_card_pull()` — core of each card pull
  - `simulation/upgrade_engine.py` (Task 9) — `attempt_upgrades()` — end-of-pull-processing step
  - `simulation/coin_economy.py` (Task 6) — `CoinLedger` — tracks all coin flow
  - `simulation/progression.py` (Task 5) — `get_unlocked_unique_count()` — unlock schedule check

  **API/Type References**:
  - `simulation/models.py:SimConfig` — `num_days`, `pack_averages`, all tables
  - `simulation/models.py:SimResult` — `daily_snapshots`, summary fields
  - `simulation/models.py:GameState` — central mutable state

  **WHY Each Reference Matters**:
  - The orchestrator CALLS every other module in sequence — it must know each module's API exactly
  - The daily loop order is critical: unlock → packs → pulls (sequential!) → upgrades → snapshot
  - `SimResult.daily_snapshots` feeds directly into all 4 dashboard charts

  **Acceptance Criteria**:

  - [ ] `pytest tests/test_orchestrator.py -v` → PASS
  - [ ] 100-day deterministic simulation completes in < 30 seconds

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: 1-day simulation produces valid state
    Tool: Bash (pytest)
    Preconditions: All engine modules (Tasks 4-9) completed and tested
    Steps:
      1. Create SimConfig with 1 day, 2 pack types (avg 1.0 each), simple upgrade tables
      2. Call run_simulation(config, rng=None)
      3. Assert: result.daily_snapshots has exactly 1 entry
      4. Assert: snapshot.day == 1
      5. Assert: snapshot.total_bluestars >= 0
      6. Assert: snapshot.coins_balance >= 0
      7. Assert: all card levels >= 1
    Expected Result: Valid single-day snapshot with non-negative values
    Failure Indicators: Empty snapshots, negative values, missing cards
    Evidence: .sisyphus/evidence/task-10-oneday.txt

  Scenario: Performance — 100-day sim under 30 seconds
    Tool: Bash (python)
    Preconditions: Full default config available
    Steps:
      1. Run: python -c "from simulation.orchestrator import run_simulation; from simulation.config_loader import load_defaults; import time; c=load_defaults(); c.num_days=100; t=time.time(); r=run_simulation(c); print(f'Time: {time.time()-t:.1f}s, Days: {len(r.daily_snapshots)}, BS: {r.total_bluestars}')"
      2. Assert: Time < 30.0s
      3. Assert: 100 daily snapshots
    Expected Result: Completes in < 30 seconds with 100 snapshots
    Failure Indicators: Timeout, > 30 seconds, wrong snapshot count
    Evidence: .sisyphus/evidence/task-10-performance.txt

  Scenario: Unique cards unlock on schedule
    Tool: Bash (pytest)
    Preconditions: Config with unlock schedule {1: 8, 5: 2} (8 on day 1, 2 more on day 5)
    Steps:
      1. Run 5-day simulation
      2. Check day 1 snapshot: total_unique_unlocked = 8
      3. Check day 4 snapshot: total_unique_unlocked = 8
      4. Check day 5 snapshot: total_unique_unlocked = 10
    Expected Result: Unique cards appear on scheduled days
    Failure Indicators: Wrong unlock count, cards missing, off-by-one
    Evidence: .sisyphus/evidence/task-10-unlock-schedule.txt
  ```

  **Commit**: YES (group with Task 11)
  - Message: `feat(sim): add simulation orchestrator with deterministic and MC modes`
  - Files: `simulation/orchestrator.py, tests/test_orchestrator.py`
  - Pre-commit: `pytest tests/test_orchestrator.py -v`

- [ ] 11. Monte Carlo Runner with Welford Statistics

  **What to do**:
  - Create `simulation/monte_carlo.py`:
    - `WelfordAccumulator` class:
      - Implements Welford's online algorithm for incremental mean + variance
      - `count: int`, `mean: float`, `m2: float`
      - `update(value: float)` — single value update
      - `result() → tuple[float, float, float]` — (mean, variance, std_dev)
      - `confidence_interval(z: float = 1.96) → tuple[float, float]` — 95% CI
    - `MCResult` dataclass:
      - `num_runs: int`
      - `bluestar_stats: WelfordAccumulator` — final bluestar total
      - `daily_bluestar_means: list[float]` — mean bluestar per day (for chart)
      - `daily_bluestar_stds: list[float]` — std per day (for confidence bands)
      - `daily_coin_balance_means: list[float]`
      - `daily_coin_balance_stds: list[float]`
      - `daily_category_level_means: dict[str, list[float]]` — per category avg level curve
      - `daily_category_level_stds: dict[str, list[float]]`
      - `completion_time: float` — seconds elapsed
    - `run_monte_carlo(config: SimConfig, num_runs: int = 100) → MCResult`
      - Validate: `num_runs ≤ 500` (hard cap), warn if > 200
      - For each run (i = 1 to num_runs):
        1. Create seeded RNG: `Random(seed=i)` for reproducibility
        2. Call `run_simulation(config, rng=rng)` → SimResult
        3. For each day, update WelfordAccumulators for that day's metrics
        4. **Do NOT store SimResult** — extract needed values then discard (memory safety)
      - After all runs: extract means and stds from accumulators
    - `DailyAccumulators` class:
      - One WelfordAccumulator per day per metric (bluestars, coins, per-category level)
      - `update_from_snapshot(day: int, snapshot: DailySnapshot)`
      - `finalize() → dict` with means and stds arrays
  - Create `tests/test_monte_carlo.py`:
    - Test: WelfordAccumulator matches numpy mean/std for known data
    - Test: 10-run MC produces valid MCResult with correct num_runs
    - Test: reproducibility — same config → same MCResult (seeded RNGs)
    - Test: confidence intervals narrow with more runs
    - Test: memory — 100-run MC doesn't store 100 SimResults (check via sys.getsizeof or mock)
    - Test: hard cap at 500 runs enforced
    - Test: 100-run × 100-day MC completes in < 120 seconds (performance)

  **Must NOT do**:
  - No Streamlit imports
  - Do NOT store all SimResult objects simultaneously (use Welford accumulators)
  - Do NOT allow num_runs > 500
  - No chart rendering
  - File must NOT exceed 200 lines

  **Recommended Agent Profile**:
  - **Category**: `ultrabrain`
    - Reason: Welford's algorithm requires precise numerical computation; memory management is critical to avoid OOM on Streamlit Cloud's 1GB limit
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (sequential after Task 10)
  - **Blocks**: Task 13, 16 (UI controls and integration tests need MC)
  - **Blocked By**: Task 10 (orchestrator)

  **References**:

  **Pattern References**:
  - `simulation/orchestrator.py` (Task 10) — `run_simulation()` is called N times with different RNGs

  **External References**:
  - Welford's algorithm: https://en.wikipedia.org/wiki/Algorithms_for_calculating_variance#Welford's_online_algorithm — Exact implementation reference
  - Python `random.Random` class: https://docs.python.org/3/library/random.html — Seeded RNG for reproducibility

  **WHY Each Reference Matters**:
  - `run_simulation()` is the function called repeatedly — MC runner wraps it with RNG injection
  - Welford's algorithm is the ONLY acceptable statistical approach (storing all runs would OOM on Streamlit Cloud)
  - Seeded RNG ensures reproducibility — same config always yields same MC results

  **Acceptance Criteria**:

  - [ ] `pytest tests/test_monte_carlo.py -v` → PASS
  - [ ] 100-run × 100-day MC completes in < 120 seconds

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Welford accuracy matches numpy
    Tool: Bash (pytest)
    Preconditions: numpy available
    Steps:
      1. Create WelfordAccumulator
      2. Feed values [2, 4, 4, 4, 5, 5, 7, 9]
      3. Assert: mean ≈ 5.0 (within 0.001)
      4. Assert: std_dev ≈ 2.0 (within 0.1)
      5. Compare with numpy: np.mean([2,4,4,4,5,5,7,9]), np.std([2,4,4,4,5,5,7,9], ddof=1)
    Expected Result: Welford matches numpy within floating point tolerance
    Failure Indicators: Mean/std deviation > 0.01 from numpy
    Evidence: .sisyphus/evidence/task-11-welford-accuracy.txt

  Scenario: MC run is reproducible
    Tool: Bash (pytest)
    Preconditions: Orchestrator (Task 10) available
    Steps:
      1. Run MC with config, num_runs=10
      2. Record final bluestar mean
      3. Run MC again with same config, num_runs=10
      4. Assert: bluestar means are IDENTICAL (exact float match)
    Expected Result: Identical results across runs with same config
    Failure Indicators: Different means (indicates unseeded or mis-seeded RNG)
    Evidence: .sisyphus/evidence/task-11-reproducibility.txt

  Scenario: Performance — 100-run × 100-day under 120 seconds
    Tool: Bash (python)
    Preconditions: Full default config, orchestrator working
    Steps:
      1. Run: python -c "from simulation.monte_carlo import run_monte_carlo; from simulation.config_loader import load_defaults; import time; c=load_defaults(); c.num_days=100; t=time.time(); r=run_monte_carlo(c, num_runs=100); print(f'Time: {time.time()-t:.1f}s, Runs: {r.num_runs}, Mean BS: {r.bluestar_stats.result()[0]:.1f}')"
      2. Assert: Time < 120.0s
      3. Assert: r.num_runs == 100
    Expected Result: Completes in < 120 seconds
    Failure Indicators: Timeout, > 120 seconds, OOM
    Evidence: .sisyphus/evidence/task-11-performance.txt
  ```

  **Commit**: YES (group with Task 10)
  - Message: `feat(sim): add simulation orchestrator with deterministic and MC modes`
  - Files: `simulation/monte_carlo.py, tests/test_monte_carlo.py`
  - Pre-commit: `pytest tests/test_monte_carlo.py -v`

- [ ] 12. Streamlit Config Editor UI — Pack & Upgrade Tables

  **What to do**:
  - Update `app.py` to be the main entry point with sidebar navigation:
    - Sidebar with page selector: "⚙️ Configuration", "▶️ Simulation", "📊 Dashboard"
    - Load default config from `config_loader.load_defaults()` into `st.session_state` on first run
    - If URL query params exist, decode and override defaults (defer URL logic to Task 13)
  - Create `pages/config_editor.py` (imported into app.py, not Streamlit multipage):
    - `render_config_editor(config: SimConfig) → SimConfig`
    - Use `st.tabs` to organize tables into groups:
      - **Tab 1: Pack Configuration**
        - `st.data_editor` for `pack_averages` — 9 rows, columns: Pack Name (read-only), 20-Day Average (editable, NumberColumn min=0, max=50, step=0.1)
        - For each pack type, expandable `st.data_editor` showing the card_types_table (total_unlocked → types_yielded)
        - "Restore Pack Defaults" button
      - **Tab 2: Upgrade Tables**
        - Sub-tabs or selectbox for category: Gold Shared, Blue Shared, Unique
        - `st.data_editor` for selected category: columns = Level, Duplicates Required, Coin Cost, Bluestar Reward
        - NumberColumn validation: all values ≥ 0, integers
        - "Restore Upgrade Defaults" button per category
      - **Tab 3: Card Economy**
        - `st.data_editor` for duplicate_ranges per category (min_pct, max_pct per level)
        - `st.data_editor` for coin_per_duplicate per category
        - Validation: min_pct ≤ max_pct, all values ≥ 0
        - "Restore Economy Defaults" button
      - **Tab 4: Progression & Schedule**
        - `st.data_editor` for progression_mapping (shared_level → unique_level)
        - `st.data_editor` for unique_unlock_schedule (day → count)
        - "Restore Defaults" button
    - All edits update `st.session_state.config` immediately
    - Use `st.column_config.NumberColumn` for type-safe validation on ALL numeric columns
  - **No separate test file needed** — UI tested via QA scenarios

  **Must NOT do**:
  - Do NOT use `st.expander` for table groups (use `st.tabs`)
  - Do NOT import from simulation engine beyond models and config_loader
  - No simulation logic in UI code
  - No chart rendering (that's Tasks 14-15)
  - Do NOT create a Streamlit multipage app (pages/ dir with automatic routing) — use manual page selection in sidebar

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Moderate complexity — many data_editor tables with validation, but following established Streamlit patterns
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `playwright`: Could test UI, but config editor is verified by checking app doesn't crash + data round-trips correctly
    - `frontend-ui-ux`: Streamlit handles layout; no custom CSS needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with Tasks 13, 14, 15)
  - **Blocks**: Task 16 (integration tests)
  - **Blocked By**: Task 2 (models), Task 3 (defaults)

  **References**:

  **Pattern References**:
  - `simulation/models.py` (Task 2) — SimConfig, PackConfig, UpgradeTable — the data shapes that tables must match
  - `simulation/config_loader.py` (Task 3) — `load_defaults()` for initial values and "Restore Defaults" functionality
  - `data/defaults/*.json` (Task 3) — Default values to populate tables

  **External References**:
  - Streamlit data_editor: https://docs.streamlit.io/develop/api-reference/data/st.data_editor — Editable table widget
  - Streamlit column_config: https://docs.streamlit.io/develop/api-reference/data/st.column_config — NumberColumn validation
  - Streamlit tabs: https://docs.streamlit.io/develop/api-reference/layout/st.tabs — Tab layout

  **WHY Each Reference Matters**:
  - `SimConfig` schema dictates what columns appear in each table and their types
  - `load_defaults()` provides both initial values AND reset targets for "Restore Defaults" buttons
  - `st.data_editor` + `column_config.NumberColumn` is the ONLY way to get validated numeric input in editable tables

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Config editor renders without errors
    Tool: Bash
    Preconditions: All dependencies installed, Tasks 1-3 complete
    Steps:
      1. Run: timeout 15 streamlit run app.py --server.headless true &
      2. Wait 5 seconds
      3. Run: curl -s -o /dev/null -w "%{http_code}" http://localhost:8501
      4. Assert: HTTP 200
      5. Kill streamlit process
    Expected Result: App launches with config editor accessible
    Failure Indicators: ImportError, HTTP 500, crash on render
    Evidence: .sisyphus/evidence/task-12-editor-launch.txt

  Scenario: No st.expander used for config tables
    Tool: Bash (grep)
    Preconditions: pages/config_editor.py exists
    Steps:
      1. Run: grep -n "st.expander" pages/config_editor.py app.py
      2. Assert: no matches found (exit code 1)
    Expected Result: Zero uses of st.expander
    Failure Indicators: Any match found
    Evidence: .sisyphus/evidence/task-12-no-expander.txt

  Scenario: Config data round-trips through session state
    Tool: Bash (python)
    Preconditions: Config editor module exists
    Steps:
      1. Run: python -c "from simulation.config_loader import load_defaults; c = load_defaults(); j = c.model_dump_json(); from simulation.models import SimConfig; c2 = SimConfig.model_validate_json(j); assert c == c2; print('Round-trip OK')"
      2. Assert: "Round-trip OK" printed
    Expected Result: Config serializes and deserializes losslessly
    Failure Indicators: ValidationError, field mismatch, assertion failure
    Evidence: .sisyphus/evidence/task-12-roundtrip.txt
  ```

  **Commit**: YES (group with Task 13)
  - Message: `feat(ui): add config editor with editable tables and URL sharing`
  - Files: `app.py, pages/config_editor.py`
  - Pre-commit: `streamlit run app.py --server.headless true & sleep 5 && curl -s -o /dev/null -w "%{http_code}" http://localhost:8501 | grep 200 && kill %1`

- [ ] 13. Streamlit Simulation Controls & URL Sharing

  **What to do**:
  - Create `pages/simulation_controls.py` (imported into app.py):
    - `render_simulation_controls(config: SimConfig) → None`
    - **Simulation Parameters**:
      - `st.number_input("Number of Days", min=1, max=730, value=100)` — deterministic max 730
      - `st.radio("Mode", ["Deterministic", "Monte Carlo"])`
      - If MC: `st.number_input("Number of Runs", min=10, max=500, value=100)`
      - If MC and runs > 200: `st.warning("⚠️ More than 200 runs may be slow. Consider 100 runs for quick results.")`
      - If MC: max days capped at 365 with explanation
      - `st.button("▶️ Run Simulation")` — triggers simulation
    - **Simulation Execution**:
      - On button click:
        - Build SimConfig from current session_state
        - Hash config: `hashlib.md5(config.model_dump_json().encode()).hexdigest()`
        - Use `@st.cache_data(ttl=3600, max_entries=10)` keyed by config hash
        - If deterministic: call `run_simulation(config)`
        - If MC: call `run_monte_carlo(config, num_runs)`
        - Show `st.progress` during MC runs (update every 10 runs)
        - Store result in `st.session_state.sim_result`
    - **URL Config Sharing**:
      - `encode_config(config: SimConfig) → str`: `config.model_dump_json()` → gzip → base64 → URL-safe string
      - `decode_config(encoded: str) → SimConfig`: reverse
      - "📋 Share Configuration" button: generates URL with `st.query_params["cfg"] = encoded`
      - Display shareable URL with `st.code(url)`
      - On app load: check `st.query_params.get("cfg")` → if present, decode and load
    - Create `simulation/url_config.py` — pure Python encode/decode functions (no Streamlit imports):
      - `encode_config(config: SimConfig) → str`
      - `decode_config(encoded: str) → SimConfig`
  - Create `tests/test_url_config.py`:
    - Test: encode/decode round-trip produces identical config
    - Test: encoded string is URL-safe (no special chars beyond base64url)
    - Test: decode of corrupted string raises clear error
    - Test: large config (all 9 packs, full upgrade tables) encodes successfully

  **Must NOT do**:
  - No chart rendering (Tasks 14-15)
  - No comparison mode
  - No data export
  - Do NOT pass 15 separate parameters to cached function — single config hash key
  - Do NOT store MC results beyond what WelfordAccumulator captures

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Integrates simulation engine with Streamlit UI, URL encoding, caching — moderate complexity
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with Tasks 12, 14, 15)
  - **Blocks**: Task 16 (integration tests)
  - **Blocked By**: Task 10 (orchestrator), Task 11 (MC runner)

  **References**:

  **Pattern References**:
  - `simulation/orchestrator.py` (Task 10) — `run_simulation()` called on button click
  - `simulation/monte_carlo.py` (Task 11) — `run_monte_carlo()` called for MC mode
  - `pages/config_editor.py` (Task 12) — Config lives in `st.session_state.config`

  **External References**:
  - Streamlit caching: https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_data — Cache decorator
  - Streamlit query_params: https://docs.streamlit.io/develop/api-reference/caching-and-state/st.query_params — URL parameter access
  - Python gzip: https://docs.python.org/3/library/gzip.html — Compression for URL encoding
  - Python base64: https://docs.python.org/3/library/base64.html — URL-safe encoding

  **WHY Each Reference Matters**:
  - `run_simulation()` and `run_monte_carlo()` are the core functions this page triggers
  - `st.cache_data` with config hash prevents re-running identical simulations
  - `st.query_params` is the mechanism for URL-based config sharing between colleagues

  **Acceptance Criteria**:

  - [ ] `pytest tests/test_url_config.py -v` → PASS

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: URL config round-trip is lossless
    Tool: Bash (pytest)
    Preconditions: url_config.py exists
    Steps:
      1. Load default config
      2. Call encode_config(config) → encoded string
      3. Call decode_config(encoded) → decoded config
      4. Assert: decoded == original (field-by-field comparison)
      5. Assert: encoded string contains only URL-safe characters
    Expected Result: Perfect round-trip, URL-safe encoding
    Failure Indicators: Field mismatch, non-URL-safe characters, decode error
    Evidence: .sisyphus/evidence/task-13-url-roundtrip.txt

  Scenario: Corrupted URL config gives clear error
    Tool: Bash (pytest)
    Preconditions: url_config.py exists
    Steps:
      1. Call decode_config("not_valid_base64!!!")
      2. Assert: raises ValueError or similar with descriptive message
      3. Call decode_config("") — empty string
      4. Assert: raises appropriate error
    Expected Result: Clear error messages, no crash
    Failure Indicators: Unhandled exception, cryptic error, silent failure
    Evidence: .sisyphus/evidence/task-13-corrupt-url.txt

  Scenario: Cache key uses single hash, not 15 params
    Tool: Bash (grep)
    Preconditions: pages/simulation_controls.py exists
    Steps:
      1. Run: grep -n "cache_data" pages/simulation_controls.py
      2. Check the cached function signature
      3. Assert: cached function takes at most 2-3 parameters (config_hash, mode, num_runs)
      4. Assert: does NOT take individual table parameters
    Expected Result: Single hash-based cache key
    Failure Indicators: Function with >5 parameters under @st.cache_data
    Evidence: .sisyphus/evidence/task-13-cache-key.txt
  ```

  **Commit**: YES (group with Task 12)
  - Message: `feat(ui): add config editor with editable tables and URL sharing`
  - Files: `pages/simulation_controls.py, simulation/url_config.py, tests/test_url_config.py`
  - Pre-commit: `pytest tests/test_url_config.py -v`

- [ ] 14. Dashboard — Bluestar Curve + Card Progression Charts

  **What to do**:
  - Create `pages/dashboard.py` (imported into app.py):
    - `render_dashboard(result: SimResult | MCResult) → None`
    - Check if `st.session_state.sim_result` exists, show "Run simulation first" if not
    - Detect result type (SimResult for deterministic, MCResult for MC)
    - **Chart 1: Bluestar Accumulation Curve**
      - X-axis: Day (1 to N)
      - Y-axis: Total Bluestars
      - Deterministic: single line from `daily_snapshots[i].total_bluestars`
      - MC: mean line + shaded 95% CI band (mean ± 1.96 * std)
      - Plotly `go.Figure` with `go.Scatter` (line) + `go.Scatter` (fill for CI band)
      - Title: "Bluestar Accumulation Over Time"
      - Interactive: hover shows exact day + value
    - **Chart 2: Card Progression by Category**
      - X-axis: Day
      - Y-axis: Average Card Level
      - 3 lines: Gold Shared, Blue Shared, Unique (different colors)
      - Deterministic: from `daily_snapshots[i].category_avg_levels`
      - MC: mean lines per category (no CI bands to avoid clutter)
      - Plotly with legend showing category names
      - Title: "Average Card Level by Category"
      - Note max levels on chart: Shared=100, Unique=10 (add horizontal reference lines)
    - Use `st.plotly_chart(fig, use_container_width=True)` for responsive sizing
    - Keep file under 150 lines — charts are straightforward Plotly code

  **Must NOT do**:
  - No per-individual-card charts (category aggregation ONLY)
  - No animation/replay
  - No data export buttons
  - No coin charts (that's Task 15)
  - File must NOT exceed 300 lines

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Chart rendering with Plotly — needs good visual design choices (colors, labels, CI bands)
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `playwright`: Could screenshot charts, but verification is that app doesn't crash + charts render
    - `frontend-ui-ux`: Plotly handles chart styling; no custom CSS

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with Tasks 12, 13, 15)
  - **Blocks**: Task 18 (QA needs charts to verify)
  - **Blocked By**: Task 10 (SimResult structure)

  **References**:

  **Pattern References**:
  - `simulation/models.py` (Task 2) — `SimResult.daily_snapshots`, `DailySnapshot` fields
  - `simulation/monte_carlo.py` (Task 11) — `MCResult.daily_bluestar_means`, `daily_bluestar_stds`, `daily_category_level_means`

  **External References**:
  - Plotly Python docs: https://plotly.com/python/line-charts/ — Line chart API
  - Plotly filled area: https://plotly.com/python/filled-area-plots/ — CI band rendering
  - Streamlit plotly_chart: https://docs.streamlit.io/develop/api-reference/charts/st.plotly_chart — Integration

  **WHY Each Reference Matters**:
  - `SimResult` and `MCResult` have different structures — chart code must handle both
  - Plotly's fill='tonexty' creates the CI band for MC results
  - `use_container_width=True` ensures charts scale responsively in Streamlit

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Charts render with deterministic results
    Tool: Bash
    Preconditions: Full simulation engine working, app.py updated
    Steps:
      1. Run: python -c "from simulation.orchestrator import run_simulation; from simulation.config_loader import load_defaults; c=load_defaults(); c.num_days=10; r=run_simulation(c); print(f'Snapshots: {len(r.daily_snapshots)}, BS: {r.total_bluestars}')"
      2. Assert: 10 snapshots generated
      3. Launch streamlit app
      4. Assert: HTTP 200 (app doesn't crash)
    Expected Result: Simulation produces data, app renders without error
    Failure Indicators: ImportError, empty snapshots, app crash
    Evidence: .sisyphus/evidence/task-14-det-charts.txt

  Scenario: No per-individual-card charts exist
    Tool: Bash (grep)
    Preconditions: pages/dashboard.py exists
    Steps:
      1. Run: grep -n "card\.id\|card\.name\|individual" pages/dashboard.py
      2. Assert: no matches plotting individual cards (category aggregation only)
    Expected Result: Only category-level aggregation in charts
    Failure Indicators: Individual card names in chart traces
    Evidence: .sisyphus/evidence/task-14-no-individual-charts.txt
  ```

  **Commit**: YES (group with Task 15)
  - Message: `feat(dashboard): add Bluestar, progression, coin, and pack ROI charts`
  - Files: `pages/dashboard.py`
  - Pre-commit: `streamlit run app.py --server.headless true & sleep 5 && curl -s -o /dev/null -w "%{http_code}" http://localhost:8501 | grep 200 && kill %1`

- [ ] 15. Dashboard — Coin Economy Flow + Pack ROI Charts

  **What to do**:
  - Add to `pages/dashboard.py` (same file as Task 14):
    - **Chart 3: Coin Economy Flow**
      - X-axis: Day
      - Y-axis: Coins
      - 3 lines/areas:
        - Daily coin income (green area)
        - Daily coin spending (red area)
        - Running coin balance (blue line, secondary Y-axis or same)
      - Deterministic: from `daily_snapshots[i].coins_earned_today`, `coins_spent_today`, `coins_balance`
      - MC: mean values only (keep it readable)
      - Title: "Coin Economy — Income vs Spending"
      - Highlight bottleneck periods: where `coins_balance ≈ 0` and upgrades were blocked
    - **Chart 4: Pack ROI Analysis**
      - Bar chart or grouped bar chart
      - X-axis: Pack Type (9 bars)
      - Y-axis: Effective Bluestars per Pack
      - Calculate: for each pack type, total bluestars attributable to cards pulled from that pack / total packs of that type opened
      - This requires tracking which pack each pull came from (CardPull.pack_name from Task 4)
      - Show as `st.plotly_chart` with bar colors by pack type
      - Title: "Pack Efficiency — Bluestars per Pack Opened"
      - Include `st.caption` with methodology note
    - Update `simulation/orchestrator.py` (or DailySnapshot) to track pack-level attribution if not already present:
      - Add `bluestars_by_pack: dict[str, float]` to SimResult — accumulated bluestar contribution per pack type
      - This may require a small addition to the orchestrator: tag each card pull with its source pack, then when that card upgrades, attribute bluestars to the pack
      - **Simplification allowed**: If exact attribution is complex, use an approximation: bluestars proportional to number of pulls from each pack type
    - Dashboard file should remain under 300 lines total (Charts 1-4)

  **Must NOT do**:
  - No pack optimization recommendations ("buy more of pack X")
  - No comparison mode
  - No data export
  - No animation
  - File must NOT exceed 300 lines

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: Chart design + coin flow visualization requires visual intuition
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with Tasks 12, 13, 14)
  - **Blocks**: Task 18 (QA)
  - **Blocked By**: Task 10 (SimResult)

  **References**:

  **Pattern References**:
  - `pages/dashboard.py` (Task 14) — Charts 1-2 already in this file, follow same Plotly patterns
  - `simulation/models.py:DailySnapshot` — `coins_earned_today`, `coins_spent_today`, `coins_balance`
  - `simulation/pack_system.py` (Task 4) — `CardPull.pack_name` for attribution

  **External References**:
  - Plotly bar charts: https://plotly.com/python/bar-charts/ — For pack ROI chart
  - Plotly multiple axes: https://plotly.com/python/multiple-axes/ — For coin balance vs income/spending

  **WHY Each Reference Matters**:
  - Charts 1-2 from Task 14 establish the Plotly patterns to follow (consistency)
  - Coin flow data comes directly from DailySnapshot — no additional computation needed
  - Pack attribution is the ONE area where orchestrator may need a small enhancement

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: All 4 charts render on dashboard
    Tool: Bash
    Preconditions: Full simulation working, Tasks 14 charts exist
    Steps:
      1. Run 10-day deterministic simulation via python script
      2. Launch streamlit app
      3. Assert: HTTP 200
      4. Run: grep -c "plotly_chart\|st\.plotly_chart" pages/dashboard.py
      5. Assert: count >= 4 (4 chart calls)
    Expected Result: All 4 charts have plotly_chart rendering calls
    Failure Indicators: Missing chart, < 4 plotly_chart calls
    Evidence: .sisyphus/evidence/task-15-all-charts.txt

  Scenario: No pack optimization recommendations
    Tool: Bash (grep)
    Preconditions: pages/dashboard.py exists
    Steps:
      1. Run: grep -in "recommend\|optimal\|best pack\|buy more\|suggestion" pages/dashboard.py
      2. Assert: no matches found
    Expected Result: No recommendation language in dashboard
    Failure Indicators: Any recommendation text found
    Evidence: .sisyphus/evidence/task-15-no-recommendations.txt
  ```

  **Commit**: YES (group with Task 14)
  - Message: `feat(dashboard): add Bluestar, progression, coin, and pack ROI charts`
  - Files: `pages/dashboard.py`
  - Pre-commit: `streamlit run app.py --server.headless true & sleep 5 && curl -s -o /dev/null -w "%{http_code}" http://localhost:8501 | grep 200 && kill %1`

- [ ] 16. Integration Tests + Edge Cases

  **What to do**:
  - Create `tests/test_integration.py` — end-to-end tests that exercise the FULL simulation pipeline:
    - **Test: Full deterministic simulation (1 day)**
      - Load defaults, run 1-day simulation
      - Assert: result has 1 snapshot, bluestars ≥ 0, coin balance ≥ 0, all cards present
    - **Test: Full deterministic simulation (100 days)**
      - Load defaults, run 100-day simulation
      - Assert: bluestars monotonically non-decreasing day over day
      - Assert: no card exceeds its max level (100 for shared, 10 for unique)
      - Assert: total_coins_earned ≥ total_coins_spent (conservation law with balance)
    - **Test: MC simulation (10 runs × 10 days)**
      - Assert: MCResult has valid means and stds
      - Assert: std > 0 (there IS variance)
      - Assert: mean bluestars > 0
    - **Test: Edge case — 0 packs per day**
      - Set all pack_averages to 0
      - Run 10-day simulation
      - Assert: no upgrades, no bluestars, no coins
    - **Test: Edge case — single day**
      - num_days = 1
      - Assert: valid result with 1 snapshot
    - **Test: Edge case — max days (730 deterministic)**
      - num_days = 730
      - Assert: completes without crash (can be slow, just don't OOM)
    - **Test: Edge case — all cards maxed**
      - Pre-set all cards to max level
      - Run simulation
      - Assert: no upgrades (already maxed), coin income from flat rewards only
    - **Test: Coin conservation**
      - After N-day simulation: `initial_coins + total_income = final_balance + total_spent`
    - **Test: URL config round-trip with full simulation**
      - Encode default config → decode → run simulation with decoded config
      - Compare results with original config simulation
      - Assert: identical results
    - **Test: Drop algorithm statistical consistency**
      - Run 50-day MC with 100 runs
      - Check shared/unique split across all runs: should be between 60-80% shared (within tolerance)
  - Update `tests/conftest.py` with shared fixtures:
    - `default_config` — loads defaults
    - `simple_config` — minimal config for fast tests
    - `seeded_rng` — reproducible random state

  **Must NOT do**:
  - No Streamlit imports in test files
  - No UI testing (that's Task 18)
  - Tests must not take > 60 seconds individually (except the 730-day stress test)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Integration tests require understanding the full pipeline and crafting meaningful edge cases
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 5 (with Tasks 17, 18)
  - **Blocks**: Task 17 (must pass before deployment prep)
  - **Blocked By**: Tasks 10, 11, 12, 13 (all implementation must be done)

  **References**:

  **Pattern References**:
  - `simulation/orchestrator.py` (Task 10) — `run_simulation()` is the main entry point
  - `simulation/monte_carlo.py` (Task 11) — `run_monte_carlo()` for MC tests
  - `simulation/url_config.py` (Task 13) — `encode_config()`, `decode_config()` for URL round-trip test
  - `tests/test_*.py` (Tasks 2-11) — Follow established test patterns from unit tests

  **WHY Each Reference Matters**:
  - Integration tests exercise the FULL pipeline — they call the same top-level functions the UI does
  - Unit tests from earlier tasks establish the assertion patterns and fixture styles to follow
  - Edge cases catch the bugs that unit tests miss (boundary conditions, conservation laws)

  **Acceptance Criteria**:

  - [ ] `pytest tests/test_integration.py -v` → PASS
  - [ ] `pytest tests/ -v` → ALL tests pass (unit + integration)

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Full test suite passes
    Tool: Bash (pytest)
    Preconditions: All implementation tasks (1-15) complete
    Steps:
      1. Run: pytest tests/ -v --tb=short
      2. Assert: 0 failures
      3. Assert: 0 errors
      4. Count total tests: should be ≥ 30
    Expected Result: All tests pass, ≥ 30 tests total
    Failure Indicators: Any failure, error, or fewer than 30 tests
    Evidence: .sisyphus/evidence/task-16-full-suite.txt

  Scenario: Edge case — zero packs produces zero progression
    Tool: Bash (pytest)
    Preconditions: Integration test file exists
    Steps:
      1. Run: pytest tests/test_integration.py::test_zero_packs -v
      2. Assert: total_bluestars == 0, total_coins_earned == 0
    Expected Result: Zero input → zero output
    Failure Indicators: Non-zero bluestars or coins with no packs
    Evidence: .sisyphus/evidence/task-16-zero-packs.txt
  ```

  **Commit**: YES
  - Message: `test: add integration tests and edge case coverage`
  - Files: `tests/test_integration.py, tests/conftest.py`
  - Pre-commit: `pytest tests/ -v`

- [ ] 17. Deployment Prep (Streamlit Cloud + README)

  **What to do**:
  - Update `.streamlit/config.toml`:
    - `[server]`: headless = true, port = 8501, enableCORS = false, enableXsrfProtection = true
    - `[theme]`: primaryColor, backgroundColor, secondaryBackgroundColor, textColor (dark-friendly defaults)
    - `[browser]`: gatherUsageStats = false
  - Update `requirements.txt` — pin versions for reproducible deploy:
    - `streamlit>=1.30.0`
    - `plotly>=5.18.0`
    - `numpy>=1.24.0`
    - `pandas>=2.0.0`
    - `pydantic>=2.5.0`
    - Remove `pytest` from requirements.txt (dev dependency only, not needed for deploy)
    - Create `requirements-dev.txt` with: `pytest>=7.0.0` + everything from requirements.txt
  - Update `README.md`:
    - Project title and description (what it does, who it's for)
    - Quick start: `pip install -r requirements.txt && streamlit run app.py`
    - Configuration guide: how to edit tables, what each table controls
    - URL sharing: how to share configs with colleagues
    - Simulation modes: deterministic vs Monte Carlo explanation
    - Dashboard: what each chart shows
    - Deployment: Streamlit Cloud instructions (connect GitHub repo, set app.py as entry)
    - Keep README under 150 lines — concise, not bloated
  - Verify Streamlit Cloud compatibility:
    - All imports are standard or in requirements.txt
    - No local file system writes (session_state only)
    - No environment variables required
    - App entry point is `app.py` at repo root

  **Must NOT do**:
  - No Dockerfile (Streamlit Cloud doesn't need one)
  - No CI/CD pipeline setup
  - No environment variables or secrets
  - README must NOT be bloated (max 150 lines)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Config files and documentation — no complex logic
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 5 (with Tasks 16, 18)
  - **Blocks**: Final Verification Wave
  - **Blocked By**: All implementation tasks (needs complete codebase to document)

  **References**:

  **External References**:
  - Streamlit Cloud deploy: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app — Deployment guide
  - Streamlit config: https://docs.streamlit.io/develop/api-reference/configuration/config.toml — Config options

  **WHY Each Reference Matters**:
  - Streamlit Cloud has specific requirements (headless, no local storage) that config must satisfy
  - README is the first thing colleagues see — must be clear and actionable

  **Acceptance Criteria**:

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: App launches with deployment config
    Tool: Bash
    Preconditions: All code complete
    Steps:
      1. Run: streamlit run app.py --server.headless true &
      2. Wait 5 seconds
      3. Run: curl -s -o /dev/null -w "%{http_code}" http://localhost:8501
      4. Assert: HTTP 200
      5. Kill process
    Expected Result: App launches successfully with config
    Failure Indicators: Config parse error, HTTP error
    Evidence: .sisyphus/evidence/task-17-deploy-launch.txt

  Scenario: No pytest in production requirements
    Tool: Bash (grep)
    Preconditions: requirements.txt exists
    Steps:
      1. Run: grep -i "pytest" requirements.txt
      2. Assert: no match (exit code 1)
      3. Run: grep -i "pytest" requirements-dev.txt
      4. Assert: match found (exit code 0)
    Expected Result: pytest in dev deps only, not production
    Failure Indicators: pytest in requirements.txt
    Evidence: .sisyphus/evidence/task-17-no-pytest-prod.txt
  ```

  **Commit**: YES
  - Message: `chore: add deployment config and finalize README`
  - Files: `.streamlit/config.toml, requirements.txt, requirements-dev.txt, README.md`
  - Pre-commit: `streamlit run app.py --server.headless true & sleep 5 && curl -s -o /dev/null -w "%{http_code}" http://localhost:8501 | grep 200 && kill %1`

- [ ] 18. Comprehensive QA

  **What to do**:
  - This task is a FULL end-to-end QA pass. The executing agent must:
    1. **Start app from clean state**: `streamlit run app.py --server.headless true`
    2. **Config Editor QA**:
       - Verify all 4 tabs render (Pack Config, Upgrade Tables, Card Economy, Progression)
       - Verify each tab has at least one `st.data_editor` table
       - Verify "Restore Defaults" buttons exist per section
       - Modify a pack average value, verify it persists in session state
    3. **Deterministic Simulation QA**:
       - Navigate to Simulation Controls
       - Set days=10, mode=Deterministic
       - Click Run
       - Verify: simulation completes, no errors in terminal
       - Navigate to Dashboard
       - Verify: all 4 charts render (Bluestar curve, card progression, coin flow, pack ROI)
       - Verify: charts have data (not empty)
    4. **Monte Carlo Simulation QA**:
       - Set mode=Monte Carlo, runs=20, days=10
       - Click Run
       - Verify: progress indicator appears
       - Verify: all 4 charts render with MC data (CI bands visible on bluestar chart)
    5. **URL Sharing QA**:
       - Click "Share Configuration"
       - Copy generated URL
       - Verify URL contains `?cfg=` parameter
       - Test decode: `python -c "from simulation.url_config import decode_config; ..."`
    6. **Edge Case QA**:
       - Set all pack averages to 0, run simulation → verify no crash, zero bluestars
       - Set days=1 → verify single snapshot
       - Set MC runs=500 → verify no warning suppression (should work but be slow)
    7. **Performance QA**:
       - Run 100-day deterministic: measure time < 30s
       - Run 100-run × 100-day MC: measure time < 120s
    8. **Guardrail QA**:
       - `grep -r "import streamlit" simulation/` → zero matches
       - `grep -rn "st\.expander" pages/ app.py` → zero matches
       - Check no file exceeds 300 lines: `wc -l simulation/*.py pages/*.py app.py`
  - Save ALL evidence to `.sisyphus/evidence/task-18-*.txt`

  **Must NOT do**:
  - No code changes (QA only — report findings)
  - If bugs found, document them clearly but do NOT fix (report to orchestrator)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Comprehensive QA requires running the full app and verifying many conditions
  - **Skills**: [`playwright`]
    - `playwright`: Needed to navigate Streamlit UI, interact with tabs, click buttons, verify chart rendering

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 5 (with Tasks 16, 17)
  - **Blocks**: Final Verification Wave
  - **Blocked By**: All implementation tasks (needs complete app)

  **References**:

  **Pattern References**:
  - ALL previous task QA scenarios — this task RE-RUNS them in context of the complete app
  - `pages/config_editor.py` (Task 12) — Tab names and structure to verify
  - `pages/dashboard.py` (Tasks 14-15) — Chart titles and types to verify
  - `pages/simulation_controls.py` (Task 13) — Controls and URL sharing to verify

  **WHY Each Reference Matters**:
  - This is the FINAL QA gate — it must verify every Must Have and Must NOT Have from the plan
  - Previous task QA tested modules in isolation; this tests them working TOGETHER

  **Acceptance Criteria**:

  - [ ] All 8 QA sections pass
  - [ ] All evidence files saved to `.sisyphus/evidence/task-18-*.txt`
  - [ ] Zero guardrail violations found

  **QA Scenarios (MANDATORY):**

  ```
  Scenario: Full app smoke test
    Tool: Bash
    Preconditions: Complete app deployed
    Steps:
      1. Run: streamlit run app.py --server.headless true &
      2. Wait 5 seconds
      3. curl http://localhost:8501 → HTTP 200
      4. Run: python -c "from simulation.orchestrator import run_simulation; from simulation.config_loader import load_defaults; c=load_defaults(); c.num_days=10; r=run_simulation(c); print(f'OK: {len(r.daily_snapshots)} days, {r.total_bluestars} BS')"
      5. Assert: "OK:" printed with valid numbers
      6. Kill streamlit
    Expected Result: App serves, simulation runs, valid output
    Failure Indicators: Any error, crash, or invalid output
    Evidence: .sisyphus/evidence/task-18-smoke-test.txt

  Scenario: Guardrails verified
    Tool: Bash
    Preconditions: All code files exist
    Steps:
      1. Run: grep -r "import streamlit" simulation/ ; echo "EXIT:$?"
      2. Assert: EXIT:1 (no matches)
      3. Run: grep -rn "st\.expander" pages/ app.py ; echo "EXIT:$?"
      4. Assert: EXIT:1 (no matches)
      5. Run: wc -l simulation/*.py pages/*.py app.py | sort -n
      6. Assert: no file exceeds 300 lines
    Expected Result: All guardrails pass
    Failure Indicators: Streamlit imports in simulation/, st.expander used, file > 300 lines
    Evidence: .sisyphus/evidence/task-18-guardrails.txt

  Scenario: Performance targets met
    Tool: Bash
    Preconditions: Full simulation engine working
    Steps:
      1. Run deterministic 100-day: time python -c "..."
      2. Assert: real time < 30 seconds
      3. Run MC 100×100: time python -c "..."
      4. Assert: real time < 120 seconds
    Expected Result: Both performance targets met
    Failure Indicators: Exceeds time limits
    Evidence: .sisyphus/evidence/task-18-performance.txt
  ```

  **Commit**: NO (QA only, no code changes)

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Rejection → fix → re-run.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .sisyphus/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `python -m py_compile` on all .py files + `pytest tests/ -v`. Review all changed files for: `# type: ignore`, bare `except:`, `print()` in prod code, unused imports, files >300 lines. Check simulation engine has ZERO Streamlit imports. Check AI slop: excessive comments, over-abstraction, generic variable names.
  Output: `Build [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Real Manual QA** — `unspecified-high`
  Start Streamlit app from clean state. Load default config. Run deterministic 100-day simulation. Verify all 4 charts render. Modify a config table value. Re-run simulation. Verify changed results. Copy URL. Open in new context. Verify config values match. Run MC mode with 50 runs. Verify progress indicator and results. Test edge cases: 0 packs/day, single day, max days.
  Output: `Scenarios [N/N pass] | Edge Cases [N tested] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual code. Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT Have" compliance. Specifically verify: no comparison mode, no data export, no auth, no DB/ORM, no per-card charts, no animation. Flag any scope additions.
  Output: `Tasks [N/N compliant] | Scope Creep [CLEAN/N issues] | VERDICT`

---

## Commit Strategy

| After Task(s) | Message | Key Files | Verification |
|------------|---------|-------|--------------|
| 1 | `chore: scaffold project structure with deps and config` | requirements.txt, .streamlit/, README.md | `pip install -r requirements.txt` |
| 2, 3 | `feat(models): add data models and default config fixtures` | simulation/models.py, data/defaults/*.json | `pytest tests/test_models.py` |
| 4, 5, 6 | `feat(core): add pack system, progression mapping, and coin economy` | simulation/pack_system.py, progression.py, coin_economy.py | `pytest tests/` |
| 7, 8 | `feat(drop): implement full card drop algorithm from Revamp Master Doc` | simulation/drop_algorithm.py | `pytest tests/test_drop_algorithm.py` |
| 9 | `feat(upgrade): add upgrade engine with gating and coin management` | simulation/upgrade_engine.py | `pytest tests/test_upgrade_engine.py` |
| 10, 11 | `feat(sim): add simulation orchestrator with deterministic and MC modes` | simulation/orchestrator.py, monte_carlo.py | `pytest tests/test_simulation.py` |
| 12, 13 | `feat(ui): add config editor with editable tables and URL sharing` | app.py, pages/*.py | `streamlit run app.py` |
| 14, 15 | `feat(dashboard): add Bluestar, progression, coin, and pack ROI charts` | pages/dashboard.py | `streamlit run app.py` |
| 16 | `test: add integration tests and edge case coverage` | tests/test_integration.py | `pytest tests/ -v` |
| 17 | `chore: add deployment config and finalize README` | .streamlit/config.toml, README.md | `streamlit run app.py --server.headless true` |

---

## Success Criteria

### Verification Commands
```bash
# All tests pass
pytest tests/ -v  # Expected: all PASS, 0 failures

# App launches
streamlit run app.py --server.headless true  # Expected: HTTP 200 on localhost:8501

# Performance: deterministic 100-day sim
python -c "from simulation.orchestrator import run_simulation; import time; t=time.time(); run_simulation(days=100); print(f'{time.time()-t:.1f}s')"  # Expected: < 30s

# Config URL round-trip
pytest tests/test_config.py::test_url_roundtrip -v  # Expected: PASS

# Drop algorithm base rates (10k pulls at balanced state)
pytest tests/test_drop_algorithm.py::test_base_rates -v  # Expected: PASS (70/30 within 3%)
```

### Final Checklist
- [ ] All "Must Have" items present and functional
- [ ] All "Must NOT Have" items verified absent
- [ ] All pytest tests pass
- [ ] Streamlit app launches without errors
- [ ] All 4 dashboard charts render correctly
- [ ] Config tables are editable with validation
- [ ] URL sharing works (encode/decode round-trip)
- [ ] Deterministic and Monte Carlo modes both work
- [ ] Performance targets met (< 30s deterministic, < 120s MC)
- [ ] Deployable to Streamlit Cloud
