"""Hero Card Tools — Drop algorithm diagram and single-pull simulator.

Provides:
1. A visual flowchart of the Variant B card drop algorithm
2. An interactive single-pull simulator for hero unique card packs
"""

from __future__ import annotations

from random import Random
from typing import Optional

import streamlit as st

from simulation.variants.variant_b.models import (
    HeroCardConfig,
    HeroCardDef,
    HeroCardRarity,
    HeroDef,
)


def render_hero_card_tools() -> None:
    st.title("Hero Card Tools")

    variant_id = st.session_state.get("active_variant", "variant_a")
    if variant_id != "variant_b":
        st.info("Switch to **Hero Card System** variant in the sidebar to use these tools.")
        return

    config: HeroCardConfig = st.session_state.configs.get("variant_b")
    if config is None:
        st.warning("No Variant B config loaded.")
        return

    tab_diagram, tab_pull = st.tabs([
        ":material/account_tree: Drop Algorithm Diagram",
        ":material/casino: Hero Card Pull Simulator",
    ])

    with tab_diagram:
        _render_drop_algorithm_diagram(config)

    with tab_pull:
        _render_hero_pull_simulator(config)


# ---------------------------------------------------------------------------
# Drop Algorithm Diagram
# ---------------------------------------------------------------------------

_DIAGRAM_CSS = """
<style>
.flow-diagram {
    font-family: 'Segoe UI', system-ui, sans-serif;
    max-width: 720px;
    margin: 0 auto;
}
.flow-node {
    border: 2px solid #555;
    border-radius: 12px;
    padding: 14px 18px;
    margin: 8px auto;
    text-align: center;
    max-width: 480px;
    font-size: 14px;
    line-height: 1.5;
}
.flow-node.start { background: #1a1a2e; color: #e0e0e0; border-color: #4a90d9; }
.flow-node.decision { background: #2d2d44; color: #f0f0f0; border-color: #f5a623;
    border-radius: 4px; transform: rotate(0deg); }
.flow-node.process { background: #1e3a2f; color: #c8e6c9; border-color: #66bb6a; }
.flow-node.outcome { background: #3e1a1a; color: #ffcdd2; border-color: #ef5350; }
.flow-node.special { background: #2a1f3d; color: #e1bee7; border-color: #ab47bc; }
.flow-arrow {
    text-align: center;
    font-size: 22px;
    color: #888;
    margin: 2px 0;
    line-height: 1.2;
}
.flow-arrow .label {
    font-size: 12px;
    color: #aaa;
    display: block;
}
.flow-split {
    display: flex;
    gap: 16px;
    justify-content: center;
    margin: 8px 0;
}
.flow-split > div { flex: 1; max-width: 340px; }
.flow-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 11px;
    font-weight: 700;
    margin: 0 2px;
}
.flow-badge.hero { background: #ff9800; color: #000; }
.flow-badge.shared { background: #2196f3; color: #fff; }
.flow-badge.joker { background: #9c27b0; color: #fff; }
.flow-badge.pity { background: #f44336; color: #fff; }
.flow-param { font-size: 12px; color: #999; margin-top: 4px; }
</style>
"""

def _render_drop_algorithm_diagram(config: HeroCardConfig) -> None:
    dc = config.drop_config
    hero_pct = f"{dc.hero_vs_shared_base_rate * 100:.0f}%"
    shared_pct = f"{(1 - dc.hero_vs_shared_base_rate) * 100:.0f}%"
    pity = dc.pity_counter_threshold
    joker_pct = f"{config.joker_drop_rate_in_regular_packs * 100:.1f}%"
    mode = dc.card_selection_mode.replace("_", " ").title()

    html = _DIAGRAM_CSS + f"""
<div class="flow-diagram">

<div class="flow-node start">
    <strong>REGULAR PACK PULL</strong><br>
    Player opens a regular pack card
</div>

<div class="flow-arrow">↓</div>

<div class="flow-node decision">
    <strong>🃏 Joker Check</strong><br>
    Roll for Hero Joker drop<br>
    <div class="flow-param">Rate: <span class="flow-badge joker">{joker_pct}</span> per pull</div>
</div>

<div class="flow-split">
    <div>
        <div class="flow-arrow"><span class="label">✓ Joker drops</span>↓</div>
        <div class="flow-node special">
            <strong>🃏 JOKER AWARDED</strong><br>
            Universal wildcard — upgrades<br>any hero card as a duplicate
        </div>
    </div>
    <div>
        <div class="flow-arrow"><span class="label">✗ No joker</span>↓</div>
        <div class="flow-node" style="border:none;padding:0;margin:0;">
            <em style="color:#888;font-size:12px;">(continue to card selection)</em>
        </div>
    </div>
</div>

<div class="flow-arrow">↓</div>

<div class="flow-node decision">
    <strong>🎯 Pity System Check</strong><br>
    Has pity counter reached threshold?<br>
    <div class="flow-param">Threshold: <span class="flow-badge pity">{pity} pulls</span> without hero card → guaranteed hero</div>
</div>

<div class="flow-split">
    <div>
        <div class="flow-arrow"><span class="label">≥ {pity} shared pulls</span>↓</div>
        <div class="flow-node process">
            <strong>→ FORCED HERO CARD</strong><br>
            Pity counter resets to 0
        </div>
    </div>
    <div>
        <div class="flow-arrow"><span class="label">Under threshold</span>↓</div>
        <div class="flow-node" style="border:none;padding:0;margin:0;">
            <em style="color:#888;font-size:12px;">(roll normally)</em>
        </div>
    </div>
</div>

<div class="flow-arrow">↓</div>

<div class="flow-node decision">
    <strong>🎲 Hero vs Shared Roll</strong><br>
    Random roll against base rate<br>
    <div class="flow-param">
        <span class="flow-badge hero">Hero {hero_pct}</span>
        <span class="flow-badge shared">Shared {shared_pct}</span>
    </div>
</div>

<div class="flow-split">
    <div>
        <div class="flow-arrow"><span class="label">🦸 Hero card</span>↓</div>
        <div class="flow-node process">
            <strong>SELECT HERO CARD</strong><br>
            Mode: <strong>{mode}</strong><br>
            <div class="flow-param">Pool: all unlocked cards<br>across all unlocked heroes</div>
        </div>
        <div class="flow-arrow">↓</div>
        <div class="flow-node process">
            <strong>COMPUTE DUPLICATES</strong><br>
            Formula: max(1, 4 − level÷10)<br>
            <div class="flow-param">Then random 1..base dupes</div>
        </div>
        <div class="flow-arrow">↓</div>
        <div class="flow-node outcome">
            <strong>⬆ UPGRADE ENGINE</strong><br>
            Dupes + Coins → Level up<br>
            Grants Bluestars + Hero XP<br>
            <div class="flow-param">Pity counter resets to 0</div>
        </div>
    </div>
    <div>
        <div class="flow-arrow"><span class="label">🟡🔵 Shared card</span>↓</div>
        <div class="flow-node process">
            <strong>SELECT SHARED CARD</strong><br>
            Lowest-level-first (catch-up)<br>
            <div class="flow-param">Weight: 1 / (level + 1)<br>
            Pool: {config.num_gold_cards} Gold + {config.num_blue_cards} Blue cards</div>
        </div>
        <div class="flow-arrow">↓</div>
        <div class="flow-node outcome">
            <strong>⬆ STANDARD UPGRADE</strong><br>
            Same upgrade engine for shared cards<br>
            <div class="flow-param">Pity counter +1</div>
        </div>
    </div>
</div>

</div>
"""
    st.components.v1.html(html, height=1050, scrolling=True)

    # Config summary below the diagram
    with st.expander("Current drop algorithm parameters"):
        col1, col2, col3 = st.columns(3)
        col1.metric("Hero rate", hero_pct)
        col1.metric("Shared rate", shared_pct)
        col2.metric("Pity threshold", pity)
        col2.metric("Selection mode", mode)
        col3.metric("Joker rate", joker_pct)
        col3.metric("Heroes unlocked", f"{len(config.heroes)}")


# ---------------------------------------------------------------------------
# Hero Card Pull Simulator
# ---------------------------------------------------------------------------

def _render_hero_pull_simulator(config: HeroCardConfig) -> None:
    st.markdown("Simulate single pulls from hero unique card packs using the actual Variant B drop algorithm.")

    if not config.heroes:
        st.warning("No heroes defined in the config.")
        return

    # Setup controls
    col1, col2 = st.columns([2, 1])
    with col1:
        unlocked_hero_ids = _get_unlocked_hero_ids(config)
        if not unlocked_hero_ids:
            st.warning("No heroes are unlocked on day 0. Adjust the unlock schedule or pick a later day.")
            return

        sim_day = st.slider(
            "Simulate at day",
            min_value=0,
            max_value=config.num_days,
            value=0,
            help="Which day to simulate — determines which heroes are unlocked",
            key="hero_pull_sim_day",
        )

        # Recalculate unlocked heroes based on selected day
        unlocked_hero_ids = []
        for day, hero_ids in sorted(config.hero_unlock_schedule.items()):
            if day <= sim_day:
                unlocked_hero_ids.extend(hero_ids)

        unlocked_heroes = [h for h in config.heroes if h.hero_id in unlocked_hero_ids]

    with col2:
        num_pulls = st.number_input(
            "Number of pulls",
            min_value=1,
            max_value=100,
            value=10,
            key="hero_pull_count",
        )
        seed = st.number_input(
            "RNG Seed (0 = random)",
            min_value=0,
            max_value=999999,
            value=0,
            key="hero_pull_seed",
        )

    if not unlocked_heroes:
        st.info(f"No heroes unlocked by day {sim_day}. Move the slider forward.")
        return

    st.caption(
        f"**Unlocked heroes at day {sim_day}:** "
        + ", ".join(f"`{h.name}`" for h in unlocked_heroes)
    )

    if st.button("Pull!", type="primary", use_container_width=True, key="do_hero_pull"):
        rng = Random(seed if seed > 0 else None)
        results = _simulate_pulls(config, unlocked_heroes, num_pulls, sim_day, rng)
        _display_pull_results(results, config, unlocked_heroes)


def _get_unlocked_hero_ids(config: HeroCardConfig) -> list[str]:
    """Get hero IDs unlocked at day 0."""
    ids = []
    for day, hero_ids in config.hero_unlock_schedule.items():
        if day <= 0:
            ids.extend(hero_ids)
    return ids


def _simulate_pulls(
    config: HeroCardConfig,
    unlocked_heroes: list[HeroDef],
    num_pulls: int,
    sim_day: int,
    rng: Random,
) -> list[dict]:
    """Simulate N pulls and return results."""
    dc = config.drop_config
    results = []
    pity_counter = 0

    # Build the card pool from unlocked heroes (starter cards only for simplicity)
    hero_cards: dict[str, list[HeroCardDef]] = {}
    for hero in unlocked_heroes:
        # Start with starter cards, add more based on a rough skill tree estimate
        starter_ids = set(hero.starter_card_ids)
        available = [c for c in hero.card_pool if c.card_id in starter_ids]
        # Rough: also add cards unlocked by early skill tree nodes proportional to sim_day
        for node in hero.skill_tree:
            if node.hero_level_required <= max(1, sim_day // 5):
                for cid in node.cards_unlocked:
                    card = next((c for c in hero.card_pool if c.card_id == cid), None)
                    if card and card not in available:
                        available.append(card)
        if available:
            hero_cards[hero.hero_id] = available

    if not hero_cards:
        return []

    for i in range(num_pulls):
        pull: dict = {"pull_number": i + 1}

        # Joker check
        if rng.random() < config.joker_drop_rate_in_regular_packs:
            pull["type"] = "joker"
            pull["description"] = "Hero Joker (universal wildcard)"
            results.append(pull)
            continue

        # Pity check
        if dc.pity_counter_threshold > 0 and pity_counter >= dc.pity_counter_threshold:
            pull_type = "hero"
            pull["pity_triggered"] = True
        else:
            pull_type = "hero" if rng.random() < dc.hero_vs_shared_base_rate else "shared"

        if pull_type == "hero":
            # Select hero card using the configured mode
            card_info = _pick_hero_card(hero_cards, dc.card_selection_mode, rng)
            if card_info:
                hero_id, card = card_info
                hero_name = next((h.name for h in unlocked_heroes if h.hero_id == hero_id), hero_id)
                base_dupes = max(1, 4 - 1 // 10)  # level 1 start
                dupes = max(1, rng.randint(1, base_dupes))
                pull["type"] = "hero"
                pull["hero_id"] = hero_id
                pull["hero_name"] = hero_name
                pull["card_id"] = card.card_id
                pull["card_name"] = card.name
                pull["rarity"] = card.rarity.value
                pull["duplicates"] = dupes
                pull["xp_on_upgrade"] = card.base_xp_on_upgrade
            pity_counter = 0
        else:
            # Shared card
            pull["type"] = "shared"
            card_type = "Gold" if rng.random() < config.num_gold_cards / (config.num_gold_cards + config.num_blue_cards) else "Blue"
            pull["card_type"] = card_type
            pull["description"] = f"{card_type} shared card"
            pity_counter += 1

        pull["pity_counter"] = pity_counter
        results.append(pull)

    return results


def _pick_hero_card(
    hero_cards: dict[str, list[HeroCardDef]],
    mode: str,
    rng: Random,
) -> Optional[tuple[str, HeroCardDef]]:
    """Pick a hero card from the available pool."""
    candidates: list[tuple[str, HeroCardDef]] = []
    for hero_id, cards in hero_cards.items():
        for card in cards:
            candidates.append((hero_id, card))

    if not candidates:
        return None

    if mode == "weighted_rarity":
        rarity_weights = {
            HeroCardRarity.COMMON: 5.0,
            HeroCardRarity.UNCOMMON: 3.0,
            HeroCardRarity.RARE: 2.0,
            HeroCardRarity.EPIC: 1.0,
            HeroCardRarity.LEGENDARY: 0.5,
        }
        weights = [rarity_weights.get(c.rarity, 1.0) for _, c in candidates]
    elif mode == "lowest_level":
        # In the simulator we don't track levels, so use inverse rarity as proxy
        rarity_weights = {
            HeroCardRarity.COMMON: 5.0,
            HeroCardRarity.UNCOMMON: 3.0,
            HeroCardRarity.RARE: 2.0,
            HeroCardRarity.EPIC: 1.0,
            HeroCardRarity.LEGENDARY: 0.5,
        }
        weights = [rarity_weights.get(c.rarity, 1.0) for _, c in candidates]
    else:
        weights = [1.0] * len(candidates)

    total = sum(weights)
    roll = rng.random() * total
    cumulative = 0.0
    for (hero_id, card), w in zip(candidates, weights):
        cumulative += w
        if roll <= cumulative:
            return hero_id, card
    return candidates[-1]


def _display_pull_results(results: list[dict], config: HeroCardConfig, heroes: list[HeroDef]) -> None:
    """Display pull simulation results."""
    if not results:
        st.warning("No results to display.")
        return

    # Summary stats
    hero_pulls = [r for r in results if r.get("type") == "hero"]
    shared_pulls = [r for r in results if r.get("type") == "shared"]
    joker_pulls = [r for r in results if r.get("type") == "joker"]
    pity_pulls = [r for r in results if r.get("pity_triggered")]

    cols = st.columns(5)
    cols[0].metric("Total pulls", len(results))
    cols[1].metric("Hero cards", len(hero_pulls))
    cols[2].metric("Shared cards", len(shared_pulls))
    cols[3].metric("Jokers", len(joker_pulls))
    cols[4].metric("Pity triggers", len(pity_pulls))

    # Visual pull results
    st.markdown("---")

    rarity_colors = {
        "COMMON": "#9e9e9e",
        "UNCOMMON": "#4caf50",
        "RARE": "#2196f3",
        "EPIC": "#9c27b0",
        "LEGENDARY": "#ff9800",
    }

    for r in results:
        pull_num = r["pull_number"]
        pity_tag = ' <span style="color:#f44336;font-weight:700;">[PITY]</span>' if r.get("pity_triggered") else ""

        if r["type"] == "joker":
            st.markdown(
                f"**#{pull_num}** — 🃏 **Hero Joker** (universal wildcard){pity_tag}",
                unsafe_allow_html=True,
            )
        elif r["type"] == "hero":
            rarity = r["rarity"]
            color = rarity_colors.get(rarity, "#fff")
            total_dupes = r["duplicates"]
            st.markdown(
                f"**#{pull_num}** — 🦸 **{r['hero_name']}** → "
                f'<span style="color:{color};font-weight:600;">{r["card_name"]}</span> '
                f'({rarity}) — **×{total_dupes}** dupes — +{r["xp_on_upgrade"]} XP{pity_tag}',
                unsafe_allow_html=True,
            )
        elif r["type"] == "shared":
            icon = "🟡" if r.get("card_type") == "Gold" else "🔵"
            st.markdown(
                f"**#{pull_num}** — {icon} **{r['description']}** *(pity: {r.get('pity_counter', 0)})*{pity_tag}",
                unsafe_allow_html=True,
            )

    # Hero card distribution
    if hero_pulls:
        st.markdown("---")
        st.markdown("**Hero card distribution**")
        hero_counts: dict[str, int] = {}
        rarity_counts: dict[str, int] = {}
        for r in hero_pulls:
            hero_counts[r["hero_name"]] = hero_counts.get(r["hero_name"], 0) + 1
            rarity_counts[r["rarity"]] = rarity_counts.get(r["rarity"], 0) + 1

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("By hero:")
            for name, count in sorted(hero_counts.items(), key=lambda x: -x[1]):
                pct = count / len(hero_pulls) * 100
                st.markdown(f"- **{name}**: {count} ({pct:.0f}%)")
        with col2:
            st.markdown("By rarity:")
            for rarity in ["COMMON", "UNCOMMON", "RARE", "EPIC", "LEGENDARY"]:
                count = rarity_counts.get(rarity, 0)
                if count > 0:
                    color = rarity_colors.get(rarity, "#fff")
                    pct = count / len(hero_pulls) * 100
                    st.markdown(
                        f'- <span style="color:{color};font-weight:600;">{rarity}</span>: {count} ({pct:.0f}%)',
                        unsafe_allow_html=True,
                    )
