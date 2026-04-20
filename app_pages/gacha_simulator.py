"""Hero Pack Pull Simulator.

Simulates opening a hero's card pack using actual Variant B config:
per-hero card pools, drop rates, and the dupe % mechanic.
"""

from __future__ import annotations

from random import Random

import streamlit as st

from simulation.variants.variant_b.models import (
    HeroCardConfig,
    HeroCardRarity,
    PremiumPackDef,
)
from simulation.variants.variant_b.drop_algorithm import (
    _find_dupe_range,
    _find_upgrade_table,
)


def render_gacha_simulator() -> None:
    st.title("Hero Card Pack Simulator")

    variant_id = st.session_state.get("active_variant", "variant_a")
    if variant_id != "variant_b":
        st.info("Switch to **Hero Card System** variant in the sidebar to use this tool.")
        return

    config: HeroCardConfig = st.session_state.configs.get("variant_b")
    if config is None:
        st.warning("No Variant B config loaded.")
        return

    if not config.premium_packs:
        st.warning("No hero packs available.")
        return

    # --- Select hero ---
    hero_packs = {p.pack_id: p for p in config.premium_packs}
    hero_names = {}
    for hero in config.heroes:
        if hero.hero_id in hero_packs:
            hero_names[hero.hero_id] = hero.name

    if not hero_names:
        st.warning("No hero packs configured.")
        return

    selected_hero = st.selectbox(
        "Select hero",
        options=list(hero_names.keys()),
        format_func=lambda x: hero_names[x],
        key="gacha_hero_select",
    )
    pack = hero_packs[selected_hero]

    # --- Controls ---
    col1, col2 = st.columns(2)
    with col1:
        num_packs = st.number_input("Packs to open", min_value=1, max_value=50, value=1, key="gacha_num_packs")
    with col2:
        seed = st.number_input("RNG seed (0 = random)", min_value=0, max_value=999999, value=0, key="gacha_seed")

    total_pulls = num_packs * ((pack.min_cards_per_pack + pack.max_cards_per_pack) // 2)
    total_cost = num_packs * pack.diamond_cost
    st.caption(f"**{total_pulls}** pulls — **{total_cost:,}** diamonds")

    if st.button("Open packs", type="primary", use_container_width=True, key="gacha_open"):
        rng = Random(seed if seed > 0 else None)
        results = _simulate(pack, config, num_packs, rng)
        _display(results, pack, config, num_packs)


def _simulate(
    pack: PremiumPackDef,
    config: HeroCardConfig,
    num_packs: int,
    rng: Random,
) -> list[dict]:
    card_info = {}
    for hero in config.heroes:
        for card in hero.card_pool:
            card_info[card.card_id] = {
                "name": card.name,
                "hero_id": hero.hero_id,
                "hero_name": hero.name,
                "rarity": card.rarity,
            }

    card_rates = [(cr.card_id, cr.drop_rate) for cr in pack.card_drop_rates]
    total_weight = sum(r for _, r in card_rates)
    results = []
    pull_num = 0

    # Track simulated card levels for dupe % calculation
    sim_card_levels: dict[str, int] = {}

    for pack_idx in range(num_packs):
        for _ in range(rng.randint(pack.min_cards_per_pack, pack.max_cards_per_pack)):
            pull_num += 1
            pull = {"pull_number": pull_num, "pack_number": pack_idx + 1}

            if rng.random() < pack.joker_rate:
                pull["type"] = "joker"
                results.append(pull)
                continue

            if total_weight > 0:
                roll = rng.random() * total_weight
                cumulative = 0.0
                selected_id = card_rates[0][0]
                for card_id, rate in card_rates:
                    cumulative += rate
                    if roll <= cumulative:
                        selected_id = card_id
                        break
            else:
                continue

            info = card_info.get(selected_id, {})
            rarity = info.get("rarity")
            card_level = sim_card_levels.get(selected_id, 1)

            # Compute dupes using the % mechanic
            dupes = _compute_sim_dupes(card_level, rarity, config, rng)

            pull["type"] = "card"
            pull["card_id"] = selected_id
            pull["card_name"] = info.get("name", selected_id)
            pull["hero_name"] = info.get("hero_name", "")
            pull["rarity"] = rarity.value if isinstance(rarity, HeroCardRarity) else str(rarity or "GRAY")
            pull["duplicates"] = dupes
            results.append(pull)

    return results


def _compute_sim_dupes(
    card_level: int,
    rarity: HeroCardRarity | None,
    config: HeroCardConfig,
    rng: Random,
) -> int:
    """Compute dupes for the simulator using the same % mechanic as the real drop algorithm."""
    if rarity is None:
        return 1

    dupe_range = _find_dupe_range(config, rarity)
    upgrade_table = _find_upgrade_table(config, rarity)

    if not dupe_range or not upgrade_table:
        return 1

    level_idx = card_level - 1
    if level_idx >= len(upgrade_table.duplicate_costs) or level_idx >= len(dupe_range.min_pct):
        return 0

    base_cost = upgrade_table.duplicate_costs[level_idx]
    min_pct = dupe_range.min_pct[level_idx]
    max_pct = dupe_range.max_pct[level_idx]
    pct = rng.uniform(min_pct, max_pct)
    return max(1, round(base_cost * pct))


def _display(results: list[dict], pack: PremiumPackDef, config: HeroCardConfig, num_packs: int) -> None:
    if not results:
        st.warning("No results.")
        return

    card_pulls = [r for r in results if r.get("type") == "card"]
    joker_pulls = [r for r in results if r.get("type") == "joker"]
    total_cost = num_packs * pack.diamond_cost

    cols = st.columns(4)
    cols[0].metric("Total pulls", len(results))
    cols[1].metric("Cards", len(card_pulls))
    cols[2].metric("Jokers", len(joker_pulls))
    cols[3].metric("Diamonds spent", f"{total_cost:,}")

    rarity_colors = {"GRAY": "#9e9e9e", "BLUE": "#2196f3", "GOLD": "#f59e0b"}

    st.markdown("---")
    for r in results:
        n = r["pull_number"]
        if r["type"] == "joker":
            st.markdown(f"**#{n}** :material/playing_cards: **JOKER** — universal wildcard")
        else:
            color = rarity_colors.get(r["rarity"], "#ccc")
            st.markdown(
                f'**#{n}** :material/person: **{r["hero_name"]}** > '
                f'<span style="color:{color};font-weight:600">{r["card_name"]}</span> '
                f'({r["rarity"]}) x{r["duplicates"]}',
                unsafe_allow_html=True,
            )

    if card_pulls:
        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**By rarity**")
            rarity_counts: dict[str, int] = {}
            for r in card_pulls:
                rarity_counts[r["rarity"]] = rarity_counts.get(r["rarity"], 0) + 1
            for rarity in ["GRAY", "BLUE", "GOLD"]:
                count = rarity_counts.get(rarity, 0)
                if count > 0:
                    color = rarity_colors.get(rarity, "#ccc")
                    pct = count / len(card_pulls) * 100
                    st.markdown(
                        f'- <span style="color:{color};font-weight:600">{rarity}</span>: {count} ({pct:.0f}%)',
                        unsafe_allow_html=True,
                    )
        with c2:
            if joker_pulls:
                joker_pct = len(joker_pulls) / len(results) * 100
                st.markdown(f"**Joker rate**: {joker_pct:.1f}% (config: {pack.joker_rate*100:.0f}%)")
