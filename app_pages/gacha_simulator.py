"""Hero Pack Pull Simulator.

Simulates opening a hero's card pack using actual Variant B config:
per-pull rarity weights, dupe % mechanic, and real pack opening logic.
"""

from __future__ import annotations

from random import Random

import streamlit as st

from simulation.variants.variant_b.models import (
    HeroCardConfig,
    HeroCardGameState,
    HeroCardRarity,
    PremiumPackDef,
)
from simulation.variants.variant_b.hero_deck import initialize_hero
from simulation.variants.variant_b.premium_packs import open_premium_pack


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
    st.caption(f"**~{total_pulls}** pulls -- **{total_cost:,}** diamonds")

    if st.button("Open packs", type="primary", width="stretch", key="gacha_open"):
        rng = Random(seed if seed > 0 else None)
        results = _simulate(pack, config, num_packs, rng)
        _display(results, pack, num_packs)


def _simulate(
    pack: PremiumPackDef,
    config: HeroCardConfig,
    num_packs: int,
    rng: Random,
) -> list[dict]:
    """Simulate opening packs using the real open_premium_pack() logic."""
    # Create a temporary game state with featured heroes — all cards unlocked
    # so the simulator can pull from the full rarity pool
    game_state = HeroCardGameState(day=0, coins=0, total_bluestars=0)
    for hero_id in pack.featured_hero_ids:
        hero_def = next((h for h in config.heroes if h.hero_id == hero_id), None)
        if hero_def:
            hero_state = initialize_hero(hero_def)
            for card in hero_state.cards.values():
                card.unlocked = True
            game_state.heroes[hero_id] = hero_state

    # Build card name/info lookup
    card_info = {}
    for hero in config.heroes:
        for card in hero.card_pool:
            card_info[card.card_id] = {
                "name": card.name,
                "hero_id": hero.hero_id,
                "hero_name": hero.name,
                "rarity": card.rarity,
            }

    results = []
    pull_num = 0

    for pack_idx in range(num_packs):
        pulls = open_premium_pack(pack, game_state, config, rng)
        for pull in pulls:
            pull_num += 1
            entry = {"pull_number": pull_num, "pack_number": pack_idx + 1}

            card_id = pull.get("card_id", "")
            is_joker = pull.get("is_joker", False)
            reward_type = pull.get("reward_type")

            if is_joker:
                entry["type"] = "joker"
            elif reward_type:
                entry["type"] = "reward"
                entry["reward_type"] = reward_type
                entry["reward_amount"] = pull.get("reward_amount", 0)
            else:
                entry["type"] = "card"
                info = card_info.get(card_id, {})
                rarity = info.get("rarity")
                entry["card_id"] = card_id
                entry["card_name"] = info.get("name", card_id)
                entry["hero_name"] = info.get("hero_name", "")
                entry["rarity"] = rarity.value if isinstance(rarity, HeroCardRarity) else str(rarity or "GRAY")
                entry["duplicates"] = pull.get("duplicates", 1)

                # Apply dupes to game state so catch-up weighting works across packs
                for hid, hstate in game_state.heroes.items():
                    if card_id in hstate.cards and hstate.cards[card_id].unlocked:
                        hstate.cards[card_id].duplicates += pull.get("duplicates", 1)

            results.append(entry)

    return results


def _display(results: list[dict], pack: PremiumPackDef, num_packs: int) -> None:
    if not results:
        st.warning("No results.")
        return

    card_pulls = [r for r in results if r.get("type") == "card"]
    joker_pulls = [r for r in results if r.get("type") == "joker"]
    reward_pulls = [r for r in results if r.get("type") == "reward"]
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
            st.markdown(f"**#{n}** :material/playing_cards: **JOKER** -- universal wildcard")
        elif r["type"] == "reward":
            st.markdown(f"**#{n}** :material/redeem: **{r['reward_type']}** x{r['reward_amount']}")
        else:
            color = rarity_colors.get(r.get("rarity", ""), "#ccc")
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
            total_dupes: dict[str, int] = {}
            for r in card_pulls:
                rarity = r.get("rarity", "GRAY")
                rarity_counts[rarity] = rarity_counts.get(rarity, 0) + 1
                total_dupes[rarity] = total_dupes.get(rarity, 0) + r.get("duplicates", 0)
            for rarity in ["GRAY", "BLUE", "GOLD"]:
                count = rarity_counts.get(rarity, 0)
                dupes = total_dupes.get(rarity, 0)
                if count > 0:
                    color = rarity_colors.get(rarity, "#ccc")
                    pct = count / len(card_pulls) * 100
                    st.markdown(
                        f'- <span style="color:{color};font-weight:600">{rarity}</span>: '
                        f'{count} cards ({pct:.0f}%), {dupes} total dupes',
                        unsafe_allow_html=True,
                    )
        with c2:
            if joker_pulls:
                joker_pct = len(joker_pulls) / len(results) * 100
                st.markdown(f"**Joker rate**: {joker_pct:.1f}% (config: {pack.joker_rate*100:.0f}%)")
            if reward_pulls:
                for r in reward_pulls:
                    st.markdown(f"**{r['reward_type']}**: {r['reward_amount']}")
