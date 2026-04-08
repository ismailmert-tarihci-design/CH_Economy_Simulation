"""Hero Pack Pull Simulator.

Simulates opening a hero's card pack at a chosen variant tier (Bronze→Diamond).
Uses actual Variant B config: per-hero card pools, drop rates, and pack variant bonuses.
"""

from __future__ import annotations

from random import Random

import streamlit as st

from simulation.variants.variant_b.models import (
    HeroCardConfig,
    HeroCardRarity,
    PackVariant,
    PremiumPackDef,
    PremiumPackRarity,
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

    # --- Select variant tier ---
    variants = config.pack_variants
    if not variants:
        st.warning("No pack variants configured. Add them in Configuration > Pack Variants.")
        return

    tier_labels = {
        v.tier.value: f"{v.tier.value} — {v.diamond_cost} diamonds, {v.cards_per_pack} cards, joker {v.joker_rate*100:.0f}%, dupe x{v.dupe_boost_multiplier:.1f}"
        for v in variants
    }
    selected_tier = st.selectbox(
        "Pack variant",
        options=list(tier_labels.keys()),
        format_func=lambda x: tier_labels[x],
        key="gacha_tier_select",
    )
    variant = next(v for v in variants if v.tier.value == selected_tier)

    # --- Controls ---
    col1, col2 = st.columns(2)
    with col1:
        num_packs = st.number_input("Packs to open", min_value=1, max_value=50, value=1, key="gacha_num_packs")
    with col2:
        seed = st.number_input("RNG seed (0 = random)", min_value=0, max_value=999999, value=0, key="gacha_seed")

    total_pulls = num_packs * variant.cards_per_pack
    total_cost = num_packs * variant.diamond_cost
    st.caption(f"**{total_pulls}** pulls — **{total_cost:,}** diamonds")

    if st.button("Open packs", type="primary", use_container_width=True, key="gacha_open"):
        rng = Random(seed if seed > 0 else None)
        results = _simulate(pack, variant, config, num_packs, rng)
        _display(results, variant, config, num_packs)


def _simulate(
    pack: PremiumPackDef,
    variant: PackVariant,
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

    for pack_idx in range(num_packs):
        for _ in range(variant.cards_per_pack):
            pull_num += 1
            pull = {"pull_number": pull_num, "pack_number": pack_idx + 1}

            if rng.random() < variant.joker_rate:
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
            dupes = max(1, round(variant.dupe_boost_multiplier))
            rarity = info.get("rarity")
            pull["type"] = "card"
            pull["card_id"] = selected_id
            pull["card_name"] = info.get("name", selected_id)
            pull["hero_name"] = info.get("hero_name", "")
            pull["rarity"] = rarity.value if isinstance(rarity, HeroCardRarity) else str(rarity or "COMMON")
            pull["duplicates"] = dupes
            results.append(pull)

    return results


def _display(results: list[dict], variant: PackVariant, config: HeroCardConfig, num_packs: int) -> None:
    if not results:
        st.warning("No results.")
        return

    card_pulls = [r for r in results if r.get("type") == "card"]
    joker_pulls = [r for r in results if r.get("type") == "joker"]
    total_cost = num_packs * variant.diamond_cost

    cols = st.columns(4)
    cols[0].metric("Total pulls", len(results))
    cols[1].metric("Cards", len(card_pulls))
    cols[2].metric("Jokers", len(joker_pulls))
    cols[3].metric("Diamonds spent", f"{total_cost:,}")

    rarity_colors = {"COMMON": "#9e9e9e", "RARE": "#2196f3", "EPIC": "#9c27b0"}

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
            for rarity in ["COMMON", "RARE", "EPIC"]:
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
                st.markdown(f"**Joker rate**: {joker_pct:.1f}% (config: {variant.joker_rate*100:.0f}%)")
