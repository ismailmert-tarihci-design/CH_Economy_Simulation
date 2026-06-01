# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Bluestar Economy Simulator — a Streamlit app for modeling game economy mechanics (card drops, dual-resource progression, pet/hero/gear systems). Used for balancing and A/B testing structural game economy variants.

## Commands

```bash
# Run the app
streamlit run app.py

# Run all tests
pytest tests/

# Run a single test file
pytest tests/test_variant_b_chapters.py

# Run a single test
pytest tests/test_variant_b_chapters.py::test_function_name

# Run with coverage
pytest tests/ --cov=simulation

# Skip slow tests
pytest tests/ -m "not slow"

# Install dependencies
pip install -r requirements.txt          # production
pip install -r requirements-dev.txt      # dev (includes pytest)
```

## Architecture

### Layer Separation

The codebase has a strict separation between **simulation engine** (`simulation/`) and **UI** (`app_pages/`, `app.py`). The simulation package has zero Streamlit imports — it is pure Python with Pydantic models. All Streamlit code lives in `app_pages/` and `app.py`.

### Simulation Engine (`simulation/`)

The only shipped variant is **Variant B (Hero Card System)**; its full daily
loop lives under `simulation/variants/variant_b/` (orchestrator, drop_algorithm,
upgrade_engine, hero_deck, skill_tree, etc.). The top-level `simulation/` package
now holds only the shared infrastructure used by Variant B and the UI.

Shared modules:
- `models.py` — Pydantic v2 models + the `Card`/`CardCategory` shared-card types
- `monte_carlo.py` — Generic Monte Carlo runner (caller passes the variant's `run_simulation` as `run_fn`)
- `config_loader.py` — Saved-results CRUD + JSON config helpers
- `pull_logger.py` — Pull-event logging
- `url_config.py` — URL config encode/decode for sharing

### Variant Framework (`simulation/variants/`)

Variants self-register as `VariantInfo` (defined in `protocol.py`), providing
their own `run_simulation`, `load_defaults`, config class, and result class.
Registration happens at import time in `variants/__init__.py`.

- `variant_b/` — Hero Card System (the sole active variant)
- `comparison.py` — Cross-result comparison utilities

The UI dispatches to Variant B's editor (`app_pages/variant_editors/`) and
dashboard (`app_pages/variant_dashboards/`).

### UI Pages (`app_pages/`)

- `config_editor.py` — Dispatches to the Variant B editor
- `simulation_controls.py` — Run deterministic or Monte Carlo simulations
- `bulk_edit_helpers.py` — CSV/Excel upload and paste for config tables
- `gacha_simulator.py` — Interactive pull simulator tool

### Data

- `data/defaults/` — Default config JSON files (pack configs, upgrade tables, progression mapping, pet/hero/gear tables)
- `data/profiles/` — Player profiles (NonPayer, Payer variants) used as simulation presets

### Config Flow

User edits config in UI → stored in `st.session_state.configs[variant_id]` → passed to simulation engine → results stored in `st.session_state`. Configs can be shared via URL encoding (JSON → gzip → base64url, handled by `url_config.py`).

## Key Conventions

- All data models use **Pydantic v2** (`BaseModel`, `model_dump_json()`, `model_validate_json()`)
- Simulation functions accept an optional `rng: Random` parameter for reproducibility
- Config validation rules are strict (e.g., pet tier probabilities must sum to 100 per tier, gear slot costs must cover all slot/level pairs)
- The orchestrator uses `DailySnapshot` dataclasses (not Pydantic) for per-day state recording
