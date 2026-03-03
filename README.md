# Bluestar Economy Simulator

A game economy simulation tool for analyzing card drop algorithms, dual-resource progression, and economic balancing. Built with Streamlit for interactive modeling and Plotly for real-time visualization.

## Features

- **Card Drop Algorithm**: Simulate drop rates and card acquisition patterns
- **Dual-Resource Progression**: Model currency and card progression systems
- **Configurable Tables**: Edit drop rates, progression curves, and simulation parameters in the browser
- **URL Sharing**: Encode/decode configuration as shareable links for team collaboration
- **Two Simulation Modes**: Deterministic (single outcome) and Monte Carlo (probability distribution)
- **Analytics Dashboard**: 4 interactive charts showing progression, distribution, and economic trends

## Quick Start

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the app:
```bash
streamlit run app.py
```

Visit `http://localhost:8501` in your browser.

## Configuration Guide

The **Config Editor** page lets you customize:
- Drop rate tables (probability per tier)
- Progression curves (level vs resource cost)
- Simulation parameters (player count, duration)

Changes are reflected immediately in previews.

### Pet, Hero, and Gear Config Inputs

The simulator supports optional table-driven pet, hero, and gear sections.

- `pet_system_config`
  - `tier_table.tiers`: tiers `1..15` with `summons_to_lvl_up` and `rarity_probabilities` (must sum to `100` per tier)
  - `level_table.levels`: per-rarity level costs for levels `1..100`
  - `duplicate_table.duplicates`: per-rarity duplicate requirements for levels `1..100`
  - `build_table.builds`: build costs for levels `1..8`
  - `eggs_per_day`: day ranges with eggs earned per day (`day_start`, `day_end`, `eggs`)
- `hero_system_config`
  - `unlock_rows`: list of `{day, hero_id, unique_cards_added}`
  - duplicate rows for same day/hero are summed deterministically
- `gear_system_config`
  - `design_income.income_table`: day ranges with `designs_per_day`
  - `slot_costs.cost_table`: slot ids `1..6`, levels `1..100`, and `design_cost`

#### Validation Rules

- Pet tier probabilities must sum to `100` per tier
- Pet tier table must include each tier `1..15` exactly once
- Pet level/duplicate tables must contain complete level coverage `1..100` per rarity
- Pet build table must contain build levels `1..8`
- Gear design day ranges must not overlap
- Gear slot cost table must fully cover all `(slot_id, level)` pairs for slots `1..6` and levels `1..100`
- Hero unlock rows require positive `day`, non-empty `hero_id`, and non-negative `unique_cards_added`

#### Happy Config Example

```json
{
  "pet_system_config": {
    "eggs_per_day": [
      {"day_start": 1, "day_end": 30, "eggs": 2}
    ]
  },
  "hero_system_config": {
    "unlock_rows": [
      {"day": 1, "hero_id": "hero_alpha", "unique_cards_added": 2}
    ]
  },
  "gear_system_config": {
    "design_income": {
      "income_table": [
        {"day_start": 1, "day_end": 10, "designs_per_day": 5}
      ]
    }
  }
}
```

#### Failure Config Example

```json
{
  "pet_system_config": {
    "tier_table": {
      "tiers": [
        {
          "tier": 1,
          "summons_to_lvl_up": 10,
          "rarity_probabilities": {
            "Common": 90,
            "Rare": 20
          }
        }
      ]
    }
  }
}
```

The example above fails validation because the tier probabilities sum to `110`, not `100`.

## URL Sharing

Share configurations with colleagues using encoded URLs. The app compresses your config (JSON → gzip → base64url) to ~2-3KB for easy sharing.

## Simulation Modes

- **Deterministic**: Single simulation run with fixed seed (reproducible results)
- **Monte Carlo**: 1000 runs with probability distribution (realistic variance analysis)

## Dashboard

Four charts analyze simulation results:
1. **Progression Over Time**: Average player level by day
2. **Resource Distribution**: Player earnings distribution by tier
3. **Drop Rate Analysis**: Actual vs expected card drop rates
4. **Economic Health**: Overall system resource flows

## Deployment (Streamlit Cloud)

1. Push repository to GitHub
2. Visit https://share.streamlit.io
3. Connect your GitHub account and repo
4. Set entry point: `app.py`
5. Deploy

## Development

Run tests:
```bash
pip install -r requirements-dev.txt
pytest tests/
```

176 unit and integration tests validate card drop logic, progression curves, and simulation accuracy.

## License

MIT License
