"""Hero Card Tools — Single-pull simulator for hero unique card packs.

Uses the actual Variant B drop algorithm parameters from the config.
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
    st.title("Hero Card Pull Simulator")

    variant_id = st.session_state.get("active_variant", "variant_a")
    if variant_id != "variant_b":
        st.info("Switch to **Hero Card System** variant in the sidebar to use this tool.")
        return

    config: HeroCardConfig = st.session_state.configs.get("variant_b")
    if config is None:
        st.warning("No Variant B config loaded.")
        return

    _render_hero_pull_simulator(config)


def _render_hero_pull_simulator(config: HeroCardConfig) -> None:
    st.markdown("Simulate single pulls from hero unique card packs using the actual Variant B drop algorithm.")

    if not config.heroes:
        st.warning("No heroes defined in the config.")
        return

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
    dc = config.drop_config
    results = []
    pity_counter = 0

    hero_cards: dict[str, list[HeroCardDef]] = {}
    for hero in unlocked_heroes:
        starter_ids = set(hero.starter_card_ids)
        available = [c for c in hero.card_pool if c.card_id in starter_ids]
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

        if rng.random() < config.joker_drop_rate_in_regular_packs:
            pull["type"] = "joker"
            pull["description"] = "Hero Joker (universal wildcard)"
            results.append(pull)
            continue

        if dc.pity_counter_threshold > 0 and pity_counter >= dc.pity_counter_threshold:
            pull_type = "hero"
            pull["pity_triggered"] = True
        else:
            pull_type = "hero" if rng.random() < dc.hero_vs_shared_base_rate else "shared"

        if pull_type == "hero":
            card_info = _pick_hero_card(hero_cards, dc.card_selection_mode, rng)
            if card_info:
                hero_id, card = card_info
                hero_name = next((h.name for h in unlocked_heroes if h.hero_id == hero_id), hero_id)
                base_dupes = max(1, 4 - 1 // 10)
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
    candidates: list[tuple[str, HeroCardDef]] = []
    for hero_id, cards in hero_cards.items():
        for card in cards:
            candidates.append((hero_id, card))

    if not candidates:
        return None

    rarity_weights = {
        HeroCardRarity.COMMON: 5.0,
        HeroCardRarity.UNCOMMON: 3.0,
        HeroCardRarity.RARE: 2.0,
        HeroCardRarity.EPIC: 1.0,
        HeroCardRarity.LEGENDARY: 0.5,
    }

    if mode in ("weighted_rarity", "lowest_level"):
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
    if not results:
        st.warning("No results to display.")
        return

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
                f"**#{pull_num}** — :material/playing_cards: **Hero Joker** (universal wildcard){pity_tag}",
                unsafe_allow_html=True,
            )
        elif r["type"] == "hero":
            rarity = r["rarity"]
            color = rarity_colors.get(rarity, "#fff")
            st.markdown(
                f"**#{pull_num}** — :material/person: **{r['hero_name']}** > "
                f'<span style="color:{color};font-weight:600;">{r["card_name"]}</span> '
                f'({rarity}) — **x{r["duplicates"]}** dupes — +{r["xp_on_upgrade"]} XP{pity_tag}',
                unsafe_allow_html=True,
            )
        elif r["type"] == "shared":
            icon = ":material/circle:" if r.get("card_type") == "Gold" else ":material/radio_button_unchecked:"
            st.markdown(
                f"**#{pull_num}** — {icon} **{r['description']}** *(pity: {r.get('pity_counter', 0)})*{pity_tag}",
                unsafe_allow_html=True,
            )

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
