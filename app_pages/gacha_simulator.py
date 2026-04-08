"""Hero Pack Pull Simulator.

Simulates opening hero-specific premium card packs using the actual
Variant B configuration values. Supports selecting a pack, choosing
how many to open, and viewing per-pull results with joker/rarity breakdown.
"""

from __future__ import annotations

from random import Random

import streamlit as st

from simulation.variants.variant_b.models import (
    HeroCardConfig,
    HeroCardRarity,
    PremiumPackDef,
)


def render_gacha_simulator() -> None:
    st.title("Hero Pack Pull Simulator")

    variant_id = st.session_state.get("active_variant", "variant_a")
    if variant_id != "variant_b":
        st.info("Switch to **Hero Card System** variant in the sidebar to use this tool.")
        return

    config: HeroCardConfig = st.session_state.configs.get("variant_b")
    if config is None:
        st.warning("No Variant B config loaded.")
        return

    if not config.premium_packs:
        st.warning("No premium packs defined. Add some in the Configuration > Premium Packs tab.")
        return

    # --- Pack selection ---
    pack_labels = {p.pack_id: f"{p.name}  ({p.pack_rarity.value} — {p.diamond_cost} diamonds, {p.cards_per_pack} cards)" for p in config.premium_packs}
    selected_id = st.selectbox(
        "Select a hero pack",
        options=list(pack_labels.keys()),
        format_func=lambda x: pack_labels[x],
        key="gacha_pack_select",
    )
    pack = next(p for p in config.premium_packs if p.pack_id == selected_id)

    # --- Pack info ---
    with st.expander("Pack details", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Diamond cost", f"{pack.diamond_cost}")
        c2.metric("Cards per pack", f"{pack.cards_per_pack}")
        c3.metric("Joker rate", f"{pack.joker_rate * 100:.1f}%")
        c4.metric("Dupe boost", f"x{pack.dupe_boost_multiplier:.1f}")

        st.caption(f"Featured heroes: **{', '.join(pack.featured_hero_ids)}**")

        if pack.card_drop_rates:
            # Build card name lookup from config heroes
            card_names = {}
            card_rarities = {}
            for hero in config.heroes:
                for card in hero.card_pool:
                    card_names[card.card_id] = card.name
                    card_rarities[card.card_id] = card.rarity.value

            total_w = sum(cr.drop_rate for cr in pack.card_drop_rates)
            rows = []
            for cr in sorted(pack.card_drop_rates, key=lambda x: -x.drop_rate):
                pct = (cr.drop_rate / total_w * 100) if total_w > 0 else 0
                rows.append({
                    "Card": card_names.get(cr.card_id, cr.card_id),
                    "Rarity": card_rarities.get(cr.card_id, "?"),
                    "Weight": f"{cr.drop_rate:.1f}",
                    "Drop %": f"{pct:.1f}%",
                })
            st.dataframe(rows, use_container_width=True, hide_index=True)

    # --- Controls ---
    col1, col2 = st.columns(2)
    with col1:
        num_packs = st.number_input("Packs to open", min_value=1, max_value=50, value=1, key="gacha_num_packs")
    with col2:
        seed = st.number_input("RNG seed (0 = random)", min_value=0, max_value=999999, value=0, key="gacha_seed")

    total_pulls = num_packs * pack.cards_per_pack
    total_cost = num_packs * pack.diamond_cost
    st.caption(f"**{total_pulls}** total pulls — **{total_cost}** diamonds")

    if st.button("Open packs", type="primary", use_container_width=True, key="gacha_open"):
        rng = Random(seed if seed > 0 else None)
        results = _simulate_pack_opening(pack, config, num_packs, rng)
        _display_results(results, pack, config, num_packs)


def _simulate_pack_opening(
    pack: PremiumPackDef,
    config: HeroCardConfig,
    num_packs: int,
    rng: Random,
) -> list[dict]:
    """Simulate opening N copies of a premium pack."""
    # Build card name/rarity lookup
    card_info = {}
    for hero in config.heroes:
        for card in hero.card_pool:
            card_info[card.card_id] = {
                "name": card.name,
                "hero_id": hero.hero_id,
                "hero_name": hero.name,
                "rarity": card.rarity,
            }

    # Build weighted pool
    card_rates = [(cr.card_id, cr.drop_rate) for cr in pack.card_drop_rates]
    total_weight = sum(r for _, r in card_rates)

    results = []
    pull_num = 0

    for pack_idx in range(num_packs):
        for draw in range(pack.cards_per_pack):
            pull_num += 1
            pull = {"pull_number": pull_num, "pack_number": pack_idx + 1}

            # Joker check
            if rng.random() < pack.joker_rate:
                pull["type"] = "joker"
                results.append(pull)
                continue

            # Card selection via weighted random
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
            base_dupes = max(1, round(1 * pack.dupe_boost_multiplier))
            pull["type"] = "card"
            pull["card_id"] = selected_id
            pull["card_name"] = info.get("name", selected_id)
            pull["hero_id"] = info.get("hero_id", "")
            pull["hero_name"] = info.get("hero_name", "")
            pull["rarity"] = info.get("rarity", HeroCardRarity.COMMON).value if isinstance(info.get("rarity"), HeroCardRarity) else str(info.get("rarity", "COMMON"))
            pull["duplicates"] = base_dupes
            results.append(pull)

    return results


def _display_results(results: list[dict], pack: PremiumPackDef, config: HeroCardConfig, num_packs: int) -> None:
    """Display pack opening results."""
    if not results:
        st.warning("No results.")
        return

    card_pulls = [r for r in results if r.get("type") == "card"]
    joker_pulls = [r for r in results if r.get("type") == "joker"]
    total_cost = num_packs * pack.diamond_cost

    # KPIs
    cols = st.columns(4)
    cols[0].metric("Total pulls", len(results))
    cols[1].metric("Cards", len(card_pulls))
    cols[2].metric("Jokers", len(joker_pulls))
    cols[3].metric("Diamonds spent", f"{total_cost:,}")

    rarity_colors = {
        "COMMON": "#9e9e9e",
        "RARE": "#2196f3",
        "EPIC": "#9c27b0",
    }

    # Pull log
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

    # Distribution
    if card_pulls:
        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**By hero**")
            hero_counts: dict[str, int] = {}
            for r in card_pulls:
                hero_counts[r["hero_name"]] = hero_counts.get(r["hero_name"], 0) + 1
            for name, count in sorted(hero_counts.items(), key=lambda x: -x[1]):
                pct = count / len(card_pulls) * 100
                st.markdown(f"- **{name}**: {count} ({pct:.0f}%)")
        with c2:
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
