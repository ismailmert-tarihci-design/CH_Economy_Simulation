"""
Variant B — Simulation Flow Reference.

Visual walkthrough of the hero card system with Mermaid diagrams,
tracing every decision path through the actual code.
"""

import streamlit as st


def render_variant_b_flow() -> None:
    st.title("Variant B -- Simulation Flow")
    st.caption(
        "Visual reference for the hero card economy. "
        "Every diagram traces directly to source code."
    )

    _render_toc()
    st.divider()
    _render_high_level_loop()
    st.divider()
    _render_initialization()
    st.divider()
    _render_pack_pull_count()
    st.divider()
    _render_hero_or_shared()
    st.divider()
    _render_hero_card_selection()
    st.divider()
    _render_shared_card_selection()
    st.divider()
    _render_duplicate_formula()
    st.divider()
    _render_upgrade_engine()
    st.divider()
    _render_hero_leveling()
    st.divider()
    _render_skill_tree()
    st.divider()
    _render_premium_packs()
    st.divider()
    _render_economy_flow()
    st.divider()
    _render_known_issues()


# ── Table of Contents ────────────────────────────────────────────────────────

def _render_toc() -> None:
    st.markdown("""
**Contents**

1. [Daily Loop (high level)](#daily-loop)
2. [Initialization](#initialization)
3. [Pack Opening / Pull Count](#pack-opening-pull-count)
4. [Hero vs Shared Decision](#hero-vs-shared-decision)
5. [Hero Card Selection (5-step bucket algorithm)](#hero-card-selection)
6. [Shared Card Selection](#shared-card-selection)
7. [Duplicate Formula](#duplicate-formula)
8. [Upgrade Engine](#upgrade-engine)
9. [Hero Leveling (XP thresholds)](#hero-leveling)
10. [Skill Tree Advancement](#skill-tree-advancement)
11. [Premium Packs](#premium-packs)
12. [Economy Flow (coins + bluestars)](#economy-flow)
13. [Known Issues / Design Notes](#known-issues-design-notes)
""")


# ── 1. Daily Loop ────────────────────────────────────────────────────────────

def _render_high_level_loop() -> None:
    st.markdown("## Daily Loop")
    st.markdown("`simulation/variants/variant_b/orchestrator.py` — `run_simulation`, lines 50-347")
    st.markdown("""
The simulation runs `num_days` iterations (default 100). Each day executes
five phases **in strict order** --- the output of each phase feeds the next.
""")

    st.markdown("""
```mermaid
flowchart TD
    START([Day N begins]) --> P1

    subgraph P1["Phase 1 --- Hero Unlocks"]
        direction LR
        P1A[Check hero_unlock_schedule for day N]
        P1B[Initialize new heroes via initialize_hero]
        P1A --> P1B
    end

    P1 --> P2

    subgraph P2["Phase 2 --- Regular Card Pulls"]
        direction TB
        P2A["Determine pull count from pack schedule<br/>(Poisson sampling per pack type)"]
        P2B{"For each pull"}
        P2C["decide_hero_or_shared()"]
        P2D["Hero path: select_hero_card() + compute dupes + coins"]
        P2E["Shared path: select_shared_card() + compute dupes + coins"]
        P2F["Check joker drop (1% per hero pull)"]
        P2A --> P2B --> P2C
        P2C -->|hero| P2D --> P2F --> P2B
        P2C -->|shared| P2E --> P2B
    end

    P2 --> P3

    subgraph P3["Phase 3 --- Premium Packs"]
        direction LR
        P3A["Check premium_pack_purchase_schedule"]
        P3B["Open packs, apply dupes + rewards to state"]
        P3A --> P3B
    end

    P3 --> P4

    subgraph P4["Phase 4 --- Upgrades"]
        direction LR
        P4A["attempt_hero_upgrades()<br/>greedy, lowest-level-first"]
        P4B["attempt_shared_upgrades()<br/>greedy, lowest-level-first"]
        P4A --> P4B
    end

    P4 --> P5

    subgraph P5["Phase 5 --- Snapshot"]
        P5A["Record DailySnapshot:<br/>coins, bluestars, hero levels,<br/>avg card levels, pull counts"]
    end

    P5 --> END([Day N complete])
```
""")

    st.markdown("""
**Key points:**
- Pulls happen **before** upgrades. All cards accumulate dupes during phase 2,
  then the upgrade engine processes them all at once in phase 4.
- Hero upgrades run **before** shared upgrades and share the same coin pool.
  If hero upgrades consume all coins, shared cards wait until next day.
- Premium packs (phase 3) are skipped entirely when
  `premium_pack_purchase_schedule` is empty (the default).
""")


# ── 2. Initialization ────────────────────────────────────────────────────────

def _render_initialization() -> None:
    st.markdown("## Initialization")
    st.markdown("`orchestrator.py` --- `_create_initial_state`, lines 350-382")

    st.markdown("""
```mermaid
flowchart LR
    subgraph Shared["Shared Cards (from Variant A Card model)"]
        G["9 Gold cards"]
        B["14 Blue cards"]
        GR["20 Gray cards"]
    end

    subgraph Heroes["Heroes (day 0 schedule)"]
        H1["Woody --- 32 cards<br/>3 GRAY starters unlocked<br/>29 cards locked"]
        H2["Cowboy --- 32 cards<br/>3 GRAY starters unlocked<br/>29 cards locked"]
    end

    subgraph State["Initial GameState"]
        S1["coins = 0"]
        S2["bluestars = 0"]
        S3["pity_counter = 0"]
    end

    Shared --> State
    Heroes --> State
```
""")

    st.markdown("""
Each hero's 32 cards break down as:
- **18 GRAY** (55%), **10 BLUE** (30%), **4 GOLD** (15%)
- 3 GRAY cards are `starter_card_ids` --- unlocked at init
- All other 29 cards have `unlocked=False`
- `skill_tree_progress = -1` (no nodes processed)

New heroes are added on their scheduled day via `_process_hero_unlocks`
(line 385). They get the same 3-starter initialization.

**Hero unlock schedule (default):**

| Day | Heroes |
|-----|--------|
| 0 | Woody, Cowboy |
| 3 | Barbarian |
| 7 | Rexx, Sunna |
| 10 | Mammon |
| 14 | Rogue, Felorc |
| 18 | Eiva |
| 21 | Gudan, Druid |
| 28 | Yasuhiro |
| 35 | Nova, Rickie |
| 42 | Raven |
| 50 | Jester |
| 60 | Munara |

Total: **17 heroes x 32 cards = 544 hero cards** + 43 shared = 587 cards in pool.
""")


# ── 3. Pack Pull Count ───────────────────────────────────────────────────────

def _render_pack_pull_count() -> None:
    st.markdown("## Pack Opening / Pull Count")
    st.markdown("`orchestrator.py` --- `_get_daily_pulls`, lines 418-488")

    st.markdown("""
```mermaid
flowchart TD
    A["Look up today's pack schedule<br/>(day-1) % len(daily_pack_schedule)"] --> B

    B{"For each pack type<br/>in schedule"}

    B --> C{"RNG mode?"}
    C -->|Monte Carlo| D["num_packs = Poisson(daily_avg)<br/>Knuth algorithm using sim RNG"]
    C -->|Deterministic| E["num_packs = round(daily_avg)"]

    D --> F
    E --> F

    F["Count total unlocked hero cards<br/>across all heroes"]
    F --> G["Look up card_types_table<br/>for this pack type"]
    G --> H["Floor-match unlocked count<br/>to get (min_cards, max_cards)"]

    H --> I{"For each pack opened"}
    I --> J["cards_in_pack = randint(min, max)"]
    J --> K["total_pulls += cards_in_pack"]
    K --> I

    I --> B
```
""")

    st.markdown("""
**Default schedule**: 9 pack types, each with `daily_avg = 1.0`.
In MC mode (Poisson with lambda=1), each pack type has ~37% chance of 0 packs,
~37% chance of 1, ~18% of 2, ~6% of 3+.

**Pack types don't affect what cards you get** --- they only determine how many
pulls you get. A StandardPackT5 pull goes through the exact same
`decide_hero_or_shared` pipeline as a PetPack pull.

**Card-types table** scales pulls with progression. Example for StandardPackT5:

| Unlocked cards | Cards per pack |
|---------------|---------------|
| 0-99 | 3-5 |
| 100-199 | 3-5 |
| 200-349 | 4-5 |
| 350-499 | 4-5 |
| 500+ | 4-5 |

At game start (6 unlocked cards), StandardPackT5 yields 3-5 cards per opening.
""")


# ── 4. Hero vs Shared ────────────────────────────────────────────────────────

def _render_hero_or_shared() -> None:
    st.markdown("## Hero vs Shared Decision")
    st.markdown("`drop_algorithm.py` --- `decide_hero_or_shared`, lines 62-85")

    st.markdown("""
```mermaid
flowchart TD
    A["Pull requested"] --> B{"pity_counter >= threshold?<br/>(default threshold = 10)"}

    B -->|Yes| C["Force HERO pull<br/>pity_counter = 0"]
    B -->|No| D{"rng.random() < hero_vs_shared_base_rate?<br/>(default = 0.50)"}

    D -->|Yes| E["HERO pull<br/>pity_counter = 0"]
    D -->|No| F["SHARED pull<br/>pity_counter += 1"]

    C --> G([Return pull type])
    E --> G
    F --> G
```
""")

    st.markdown("""
**Pity system**: After 10 consecutive shared-only pulls, the next pull is
guaranteed to be a hero card. The counter resets to 0 on every hero pull.

With a 50% base rate and pity at 10, the effective hero rate is slightly above
50% because pity kicks in for unlucky streaks.
""")


# ── 5. Hero Card Selection ───────────────────────────────────────────────────

def _render_hero_card_selection() -> None:
    st.markdown("## Hero Card Selection")
    st.markdown("`drop_algorithm.py` --- `select_hero_card`, lines 111-208")

    st.markdown("""
```mermaid
flowchart TD
    A["Collect eligible heroes<br/>(those with >= 1 unlocked card)"] --> B["Sort heroes by level ascending"]

    B --> C["Split into 3 buckets:<br/>Bottom / Middle / Top<br/>(bucket_size = n//3, remainder to bottom)"]

    C --> D["Weighted random bucket pick<br/>bottom=0.40, mid=0.35, top=0.25<br/>(empty buckets excluded)"]

    D --> E["Pick hero from bucket<br/>weight = 1.0 per hero"]
    E --> E2{"Same hero as last pull?"}
    E2 -->|Yes| E3["weight *= 0.3^streak_count<br/>(anti-streak decay)"]
    E2 -->|No| E4["weight = 1.0"]
    E3 --> F
    E4 --> F

    F["Roll rarity from hero's<br/>UNLOCKED card rarities only"]
    F --> F2["Weights: GRAY=0.64, BLUE=0.30, GOLD=0.06<br/>(only available rarities participate)"]

    F2 --> G["Pick card of chosen rarity<br/>weight = 1 / (card.level + 1)<br/>(lowest-level catch-up)"]

    G --> H(["Return (hero_id, card_id)"])
```
""")

    st.markdown("""
**Five-step algorithm explained:**

1. **Eligibility**: Only heroes with at least one unlocked card participate.
   A newly unlocked hero with 3 starter GRAY cards is eligible immediately.

2. **Bucket split**: With 2 heroes at equal levels, both go to the bottom bucket
   (middle and top are empty). With 5 heroes, bottom gets 3, middle gets 1, top gets 1.

3. **Bucket weighting**: The 40/35/25 split means lower-level heroes are
   favored, creating natural catch-up for behind heroes.

4. **Anti-streak**: Pulling the same hero consecutively incurs exponential decay.
   After 2 consecutive Woody pulls, Woody's weight = `1.0 * 0.3^2 = 0.09`
   vs 1.0 for other heroes in the same bucket.

5. **Rarity gating**: At game start, heroes only have GRAY cards unlocked.
   The rarity roll is restricted to available rarities, so BLUE and GOLD cards
   **cannot drop until the skill tree unlocks them**. This is the critical
   progression gate.
""")


# ── 6. Shared Card Selection ─────────────────────────────────────────────────

def _render_shared_card_selection() -> None:
    st.markdown("## Shared Card Selection")
    st.markdown("`drop_algorithm.py` --- `select_shared_card`, lines 215-240")

    st.markdown("""
```mermaid
flowchart TD
    A["All 43 shared cards<br/>(9 Gold + 14 Blue + 20 Gray)"] --> B["Sort by level ascending"]
    B --> C["Weight each card:<br/>w = 1 / (level + 1)"]
    C --> D["Weighted random pick<br/>(or lowest level in deterministic mode)"]
    D --> E(["Return Card object"])
```
""")

    st.markdown("""
**No category selection.** Unlike Variant A which chooses category first
(Gold vs Blue vs Unique), Variant B picks from the flat pool of all 43 cards.

Early-game distribution by pure count weighting (all at level 1):
- GRAY_SHARED: 20/43 = **46.5%** of shared pulls
- BLUE_SHARED: 14/43 = **32.6%**
- GOLD_SHARED: 9/43 = **20.9%**

As cards level up unevenly, the `1/(level+1)` weighting shifts pulls toward
lower-level cards --- same catch-up mechanic as hero cards.
""")


# ── 7. Duplicate Formula ─────────────────────────────────────────────────────

def _render_duplicate_formula() -> None:
    st.markdown("## Duplicate Formula")
    st.markdown("`drop_algorithm.py` --- `compute_hero_duplicates` (line 267) / `compute_shared_duplicates` (line 360)")

    st.markdown("""
```mermaid
flowchart TD
    A["Card pulled at level L, rarity R"] --> B["Look up upgrade table for rarity R"]
    B --> C["dupe_cost = duplicate_costs[L - 1]<br/>(dupes needed for next level)"]
    C --> D["Look up dupe range for rarity R"]
    D --> E["min_pct = min_pct[L - 1]<br/>max_pct = max_pct[L - 1]"]
    E --> F["pct = uniform(min_pct, max_pct)"]
    F --> G["dupes = max(1, round(dupe_cost * pct))"]
    G --> H{"L - 1 >= table length?"}
    H -->|Yes| I["Return 0<br/>(card is at max level)"]
    H -->|No| J(["Return dupes"])
```
""")

    st.markdown("""
**The formula: `dupes = max(1, round(next_level_dupe_cost * uniform(min%, max%)))`**

Each pull gives you a **fraction** of what you need for the next upgrade.
The percentages taper at higher levels:

**Hero GRAY card example:**

| Card Level | Dupe Cost | min% | max% | Expected Dupes | Pulls to Upgrade |
|-----------|----------|------|------|---------------|-----------------|
| 1 | 10 | 80% | 90% | 8-9 | ~1-2 |
| 2 | 12 | 75% | 85% | 9-10 | ~1-2 |
| 5 | 32 | 60% | 70% | 19-22 | ~1-2 |
| 8 | 78 | 45% | 55% | 35-43 | ~2-3 |
| 9 | 150 | 40% | 50% | 60-75 | ~2-3 |

**Coin income per dupe** is also looked up from the dupe range table
(`coins_per_dupe[L-1]`). GRAY hero cards at level 1 earn 25 coins per dupe,
so a pull of 8 dupes earns `max(1, 8 * 25)` = 200 coins.

**Shared cards** use the same formula with separate tables per category.
GRAY_SHARED at level 1: 80-90% of 8 = 6-7 dupes, earning `6 * 3` = 18 coins.
""")


# ── 8. Upgrade Engine ────────────────────────────────────────────────────────

def _render_upgrade_engine() -> None:
    st.markdown("## Upgrade Engine")
    st.markdown("`upgrade_engine.py` --- `attempt_hero_upgrades` (line 43) / `attempt_shared_upgrades` (line 182)")

    st.markdown("""
```mermaid
flowchart TD
    A(["Start upgrade loop"]) --> B["Collect ALL unlocked cards<br/>across ALL heroes + their tables"]
    B --> C["Sort by level ascending"]
    C --> D{"For each candidate<br/>(lowest level first)"}

    D --> E{"card.duplicates + jokers >= dupe_cost<br/>AND coins >= coin_cost?"}

    E -->|No| F["Skip, try next card"]
    F --> D

    E -->|Yes| G["Execute upgrade"]

    subgraph G["Execute Upgrade"]
        direction TB
        G1["Consume dupes from card<br/>(use jokers for shortfall)"]
        G2["Deduct coins"]
        G3["card.level += 1"]
        G4["Grant bluestars"]
        G5["Grant Hero XP to this hero"]
        G1 --> G2 --> G3 --> G4 --> G5
    end

    G --> H{"Hero leveled up?"}
    H -->|Yes| I["Advance skill tree<br/>(may unlock new cards)"]
    H -->|No| J["BREAK --- restart scan<br/>from lowest level"]
    I --> J
    J --> B

    D -->|No more candidates| K(["Done --- return events"])
```
""")

    st.markdown("""
**Greedy with restart**: After each successful upgrade, the loop **breaks and
restarts** the scan from the lowest-level card. This ensures the
lowest-level-first priority is maintained even when an upgrade changes the
ordering (e.g., a level 1 card becomes level 2, and now a different level 1
card should go first).

**Jokers as wildcards**: If a card needs 10 dupes but only has 7, the engine
checks if the hero has >= 3 jokers. If so, it uses 3 jokers + 7 card dupes.
Jokers are per-hero --- Woody's jokers can't help Cowboy.

**Shared card upgrades** use the same greedy loop but simpler: no XP, no
jokers, no skill tree checks. They run **after** hero upgrades and share the
same coin pool.

**Default upgrade costs (hero cards):**

| Rarity | Lv1 Dupes | Lv1 Coins | Lv1 Bluestars | Lv1 XP |
|--------|----------|----------|--------------|--------|
| GRAY | 10 | 250 | 50 | 10 |
| BLUE | 20 | 250 | 100 | 20 |
| GOLD | 20 | 250 | 150 | 30 |

Costs escalate: GRAY level 9 needs 150 dupes + 1,250 coins for 250 BS + 30 XP.
""")


# ── 9. Hero Leveling ─────────────────────────────────────────────────────────

def _render_hero_leveling() -> None:
    st.markdown("## Hero Leveling")
    st.markdown("`upgrade_engine.py` --- `_check_hero_level_up`, lines 149-166")

    st.markdown("""
```mermaid
flowchart TD
    A["Hero upgrade completed<br/>XP granted to hero"] --> B{"hero.xp >= xp_per_level[level - 1]?"}
    B -->|No| C(["No level up"])
    B -->|Yes| D["hero.xp -= threshold<br/>hero.level += 1"]
    D --> E{"Still enough XP<br/>for another level?"}
    E -->|Yes| D
    E -->|No| F(["Level-up complete<br/>trigger skill tree check"])
```
""")

    st.markdown("""
**XP is consumed, not cumulative.** When a hero reaches the threshold for level
N, that amount is subtracted from their XP pool. If they have enough left over,
they level again immediately (multi-level-up in one step).

**Default XP thresholds:** `[50, 75, 100, 125, 150, 175, ...]` (50 + 25*i)

| Hero Level | XP Needed | Cumulative XP | GRAY Upgrades Needed |
|-----------|----------|--------------|---------------------|
| 1 -> 2 | 50 | 50 | 5 upgrades (at 10 XP each) |
| 2 -> 3 | 75 | 125 | 7-8 more |
| 3 -> 4 | 100 | 225 | 10 more |
| 4 -> 5 | 125 | 350 | 12-13 more |
| 9 -> 10 | 250 | 1,475 | 25 more |

BLUE upgrades give 20 XP and GOLD give 30 XP, so higher rarity cards
accelerate hero leveling --- but they don't enter the pool until the skill
tree unlocks them.
""")


# ── 10. Skill Tree ───────────────────────────────────────────────────────────

def _render_skill_tree() -> None:
    st.markdown("## Skill Tree Advancement")
    st.markdown("`skill_tree.py` --- `check_and_advance_skill_tree`, lines 15-42")

    st.markdown("""
```mermaid
flowchart TD
    A["Hero leveled up to level L"] --> B{"For each node in skill_tree<br/>(linear order)"}

    B --> C{"node.index <= skill_tree_progress?"}
    C -->|Yes| D["Already unlocked --- skip"]
    D --> B

    C -->|No| E{"L >= node.hero_level_required?"}
    E -->|No| F(["STOP --- linear tree,<br/>can't skip ahead"])
    E -->|Yes| G["Activate node"]

    subgraph G["Activate Node"]
        direction TB
        G1["skill_tree_progress = node.index"]
        G2["unlock_cards(hero, node.cards_unlocked)"]
        G3["Record perk_label (display only)"]
        G1 --> G2 --> G3
    end

    G --> B
```
""")

    st.markdown("""
**Linear progression**: Nodes must be activated in order. You cannot skip
node 5 to reach node 6, even if the hero's level exceeds node 6's requirement.

**Default tree structure** (per hero, 30 nodes):

Each node unlocks 1 card. Cards are distributed in the order they appear in
`card_pool`: GRAY cards first (nodes 0-14), then BLUE (nodes 15-24), then
GOLD (nodes 25-28). Node 29 has no card (perk-only).

| Node | Required Level | Unlocks |
|------|---------------|---------|
| 0 | 2 | 4th GRAY card |
| 1 | 3 | 5th GRAY card |
| ... | ... | ... |
| 14 | 16 | 18th GRAY card (last) |
| 15 | 17 | 1st BLUE card |
| 16 | 18 | 2nd BLUE card |
| ... | ... | ... |
| 24 | 26 | 10th BLUE card (last) |
| 25 | 27 | 1st GOLD card |
| ... | ... | ... |
| 28 | 30 | 4th GOLD card (last) |
| 29 | 31 | Perk only |

**This means:**
- BLUE cards don't enter the drop pool until **hero level 17**
- GOLD cards don't enter until **hero level 27**
- A hero needs ~3,800 cumulative XP to reach level 17 (from GRAY upgrades alone)
""")


# ── 11. Premium Packs ────────────────────────────────────────────────────────

def _render_premium_packs() -> None:
    st.markdown("## Premium Packs")
    st.markdown("`premium_packs.py` --- `open_premium_pack`, lines 117-253")

    st.markdown("""
```mermaid
flowchart TD
    A["Open premium pack<br/>num_cards = randint(min, max)"] --> B{"card_count < num_cards?"}

    B -->|No| REWARDS

    B -->|Yes| C{"rng.random() < joker_rate?<br/>(default 2%)"}
    C -->|Yes| JOKER["Add joker to featured hero<br/>card_count += 1"]
    JOKER --> B

    C -->|No| D{"Determine rarity"}

    subgraph D["Rarity Selection"]
        direction TB
        D1{"Gold guarantee active AND<br/>last card AND no gold yet?"}
        D1 -->|Yes| D2["Force GOLD"]
        D1 -->|No| D3{"Already got gold?"}
        D3 -->|Yes| D4["Roll from default_rarity_weights<br/>(0.60 gray, 0.30 blue, 0.10 gold)"]
        D3 -->|No| D5{"draw_idx < rarity_schedule length?"}
        D5 -->|Yes| D6["Roll from pull_rarity_schedule[idx]"]
        D5 -->|No| D4
    end

    D --> E["_pick_card_by_rarity_catchup<br/>(featured hero's unlocked cards only)"]
    E --> F{"Found a card?"}
    F -->|No| G["Fallback: try other rarities"]
    G --> H{"Any card found?"}
    H -->|No| BREAK(["Break --- no cards available"])
    H -->|Yes| RESOLVE
    F -->|Yes| RESOLVE

    RESOLVE["Compute dupes<br/>(with optional %-of-cost override)"]
    RESOLVE --> I["got_gold = true if card is GOLD"]
    I --> J["card_count += 1"]
    J --> B

    REWARDS["Add hero_tokens reward<br/>Roll additional rewards (coins, bluestars)"]
    REWARDS --> DONE(["Return pull results"])
```
""")

    st.markdown("""
**Default rarity schedule** (4 pulls, fixed at min=max=4 cards):

| Pull # | GRAY | BLUE | GOLD | Intent |
|--------|------|------|------|--------|
| 1 | 60% | 30% | 10% | Standard distribution |
| 2 | 15% | 75% | 10% | BLUE-heavy |
| 3 | 15% | 75% | 10% | BLUE-heavy |
| 4 | 0% | 0% | 100% | Guaranteed GOLD |

After pulling any GOLD, remaining pulls switch to `default_rarity_weights`
(60/30/10). If the guarantee can't deliver GOLD (no GOLD cards unlocked),
it falls back to whatever rarity is available.

**By default, premium packs are not purchased** (`purchase_schedule` is empty).
The user must configure a purchase schedule to activate premium pack economics.
""")


# ── 12. Economy Flow ─────────────────────────────────────────────────────────

def _render_economy_flow() -> None:
    st.markdown("## Economy Flow")
    st.markdown("`orchestrator.py` --- coin and bluestar tracking throughout the daily loop")

    st.markdown("""
```mermaid
flowchart TD
    subgraph Income["Coin Income Sources"]
        I1["Hero card pull<br/>dupes * coins_per_dupe<br/>(GRAY lv1: 8 dupes * 25 = 200)"]
        I2["Shared card pull<br/>dupes * coins_per_dupe<br/>(GRAY_SHARED lv1: 6 * 3 = 18)"]
        I3["Premium pack rewards<br/>(20% chance of 500 coins)"]
    end

    subgraph Spend["Coin Spend"]
        S1["Hero card upgrade<br/>(GRAY lv1: 250 coins)"]
        S2["Shared card upgrade<br/>(GRAY_SHARED lv1: 25 coins)"]
    end

    subgraph BS["Bluestar Income"]
        B1["Hero card upgrade<br/>(GRAY lv1: 50 BS)"]
        B2["Shared card upgrade<br/>(GRAY_SHARED lv1: 5 BS)"]
        B3["Premium pack rewards<br/>(10% chance of 50 BS)"]
    end

    Income --> POOL["game_state.coins"]
    POOL --> Spend

    BS --> TOTAL["game_state.total_bluestars"]
```
""")

    st.markdown("""
**Coin economics at a glance:**

Hero pulls are the primary coin engine. A single hero GRAY pull at level 1
earns ~200 coins, while a shared GRAY pull earns ~18 coins --- **10x difference**.

But hero upgrades are expensive (250 coins at level 1), while shared upgrades
are cheap (25 coins). The system is designed so hero pulls fund hero upgrades,
and the overflow trickles down to shared card upgrades.

**Bluestar economics:**

| Source | Amount | Frequency |
|--------|--------|-----------|
| Hero GRAY upgrade | 50 BS | Every ~1-2 hero GRAY pulls |
| Hero BLUE upgrade | 100 BS | Rare (BLUE unlocks at hero lv17) |
| Hero GOLD upgrade | 150 BS | Very rare (GOLD unlocks at hero lv27) |
| Shared GRAY_SHARED upgrade | 5 BS | Every ~1-2 shared GRAY pulls |
| Shared GOLD_SHARED upgrade | 30 BS | Less frequent |

Hero card upgrades are the dominant bluestar source. Shared cards contribute
a steady but small bluestar stream.
""")


# ── 13. Known Issues ─────────────────────────────────────────────────────────

def _render_known_issues() -> None:
    st.markdown("## Known Issues / Design Notes")

    st.markdown("""
### BLUE/GOLD cards take a long time to unlock

The default skill tree distributes cards in rarity order: all GRAY cards
fill nodes 0-14, BLUE fills 15-24, GOLD fills 25-28. Since each node
requires 1 additional hero level, BLUE cards don't enter the pool until
**hero level 17** and GOLD until **hero level 27**.

Reaching level 17 from GRAY-only upgrades (10 XP each) requires ~3,800
cumulative XP, or roughly **380 GRAY upgrades on one hero**. This may be
intentionally slow for long-term retention, but it means the early game is
entirely GRAY-dominated.

**Possible tuning levers:**
- Interleave rarities in the skill tree (mix BLUE cards into earlier nodes)
- Increase XP rewards for GRAY upgrades
- Lower the hero level requirements on skill tree nodes
- Add BLUE cards to starter_card_ids

---

### Shared card selection has no category weighting

`select_shared_card` picks from the flat pool of 43 cards weighted only by
level. There's no configurable rate for Gold vs Blue vs Gray shared pulls
(unlike Variant A which selects category first). GRAY_SHARED dominates at
~47% due to having 20 of 43 cards.

---

### Pack types are volume-only, not content-differentiated

All 9 pack types produce pulls through the same `decide_hero_or_shared`
pipeline. A "HeroPack" doesn't guarantee hero cards --- it just gives you
1-2 pulls (at the 0-unlocked threshold). Pack differentiation is purely in
how many cards you get, not what kind.

---

### Premium pack card pulls don't generate coin income

When a premium pack pulls a hero card (not joker, not reward), the
orchestrator adds dupes to the card but does **not** compute coin income
from those dupes. Regular pulls earn `dupes * coins_per_dupe`, but premium
card pulls earn 0 coins. Premium packs only generate coins through
additional rewards (20% chance of 500 coins per pack).

---

### shared_hero_level / shared_hero_xp fields are unused

`HeroCardGameState` has `shared_hero_xp` and `shared_hero_level` fields,
and `HeroCardConfig` has `shared_xp_per_level`. These represent a "shared
hero level" across all heroes. However, the orchestrator never updates these
fields. The daily snapshot's `shared_hero_level` is computed as `max(hero
levels)` instead. The shared XP system is defined but not wired in.
""")
