"""Hero Unique Pack Pull Simulator.

Simulates opening a hero's Hero Unique Pack using the actual Variant B logic:
MainUpgradeCards + BonusCards split, PullSinceUniqueGold-based rarity, and
pack-level jokers / coins / hero tokens.
"""

from __future__ import annotations

from random import Random

import pandas as pd
import streamlit as st

from simulation.variants.variant_b.models import (
    HeroCardConfig,
    HeroCardGameState,
    PremiumPackDef,
)
from simulation.variants.variant_b.hero_deck import initialize_hero
from simulation.variants.variant_b.premium_packs import open_premium_pack


RARITY_COLORS = {"GRAY": "#9e9e9e", "BLUE": "#2196f3", "GOLD": "#f59e0b"}


def render_gacha_simulator() -> None:
    st.title("Hero Unique Pack Simulator")
    st.caption(
        "Simulates the new pack structure: 5 MainUpgradeCards + 1-3 BonusCards, "
        "rarity rolled per PullSinceUniqueGold (default rates after a gold lands), "
        "plus pack-level jokers, coins, and hero tokens."
    )

    variant_id = st.session_state.get("active_variant", "variant_b")
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
    hero_names = {hero.hero_id: hero.name for hero in config.heroes if hero.hero_id in hero_packs}
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

    # --- Pack composition summary ---
    with st.expander("Pack composition (current config)", expanded=True):
        _render_composition_summary(pack)

    # --- Controls ---
    col1, col2, col3 = st.columns(3)
    with col1:
        num_packs = st.number_input("Packs to open", min_value=1, max_value=200, value=1, key="gacha_num_packs")
    with col2:
        seed = st.number_input("RNG seed (0 = random)", min_value=0, max_value=999999, value=0, key="gacha_seed")
    with col3:
        view_mode = st.selectbox(
            "View",
            options=["Per-pull detail", "Aggregate only"],
            index=0,
            key="gacha_view_mode",
        )

    avg_main = (pack.main_cards_min + pack.main_cards_max) / 2
    avg_bonus = (pack.bonus_cards_min + pack.bonus_cards_max) / 2
    total_cost = num_packs * pack.diamond_cost
    st.caption(
        f"**~{int(round(num_packs * (avg_main + avg_bonus)))}** card pulls "
        f"({int(round(num_packs * avg_main))} main + ~{int(round(num_packs * avg_bonus))} bonus) "
        f"-- **{total_cost:,}** diamonds"
    )

    if st.button("Open packs", type="primary", width="stretch", key="gacha_open"):
        rng = Random(seed if seed > 0 else None)
        results = _simulate(pack, config, num_packs, rng)
        st.session_state["gacha_last_results"] = results
        st.session_state["gacha_last_pack"] = pack
        st.session_state["gacha_last_num_packs"] = num_packs

    results = st.session_state.get("gacha_last_results")
    if results and st.session_state.get("gacha_last_pack") is pack:
        _display(results, pack, st.session_state.get("gacha_last_num_packs", 1), view_mode)


def _render_composition_summary(pack: PremiumPackDef) -> None:
    cA, cB, cC = st.columns(3)
    with cA:
        st.markdown("**Cards**")
        st.markdown(
            f"- Main: **{pack.main_cards_min}-{pack.main_cards_max}** (100% rate)\n"
            f"- Bonus: **{pack.bonus_cards_min}-{pack.bonus_cards_max}** (100% rate)"
        )
    with cB:
        st.markdown("**Pack-level rewards**")
        st.markdown(
            f"- Jokers: **{pack.joker_min}-{pack.joker_max}** @ {pack.joker_probability*100:.0f}%\n"
            f"- Coins: **{pack.coins_min}-{pack.coins_max}** @ {pack.coins_probability*100:.0f}%\n"
            f"- Hero tokens: **{pack.hero_tokens_min}-{pack.hero_tokens_max}** @ {pack.hero_tokens_probability*100:.0f}%"
        )
    with cC:
        st.markdown("**Dupe % of required (main / bonus)**")
        rows = []
        for r in ("GRAY", "BLUE", "GOLD"):
            main_min = pack.main_dupe_min_pct.get(r, 1.0) * 100
            main_max = pack.main_dupe_max_pct.get(r, 1.1) * 100
            bonus_min = pack.bonus_dupe_min_pct.get(r, 0.2) * 100
            bonus_max = pack.bonus_dupe_max_pct.get(r, 0.4) * 100
            rows.append({
                "Rarity": r,
                "Main %": f"{main_min:.0f}-{main_max:.0f}",
                "Bonus %": f"{bonus_min:.0f}-{bonus_max:.0f}",
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    st.markdown("**Rarity per PullSinceUniqueGold** (then default after gold)")
    sched_rows = []
    for i, r in enumerate(pack.pull_rarity_schedule):
        sched_rows.append({
            # Keep this column all-strings: the final "After Gold" row makes a
            # mixed int/str column that PyArrow can't serialize for st.dataframe.
            "PullSinceUniqueGold": str(i + 1),
            "Gray %": round(r.gray_weight * 100, 1),
            "Blue %": round(r.blue_weight * 100, 1),
            "Gold %": round(r.gold_weight * 100, 1),
        })
    sched_rows.append({
        "PullSinceUniqueGold": "After Gold",
        "Gray %": round(pack.default_rarity_weights.gray_weight * 100, 1),
        "Blue %": round(pack.default_rarity_weights.blue_weight * 100, 1),
        "Gold %": round(pack.default_rarity_weights.gold_weight * 100, 1),
    })
    st.dataframe(pd.DataFrame(sched_rows), hide_index=True, width="stretch")


def _simulate(
    pack: PremiumPackDef,
    config: HeroCardConfig,
    num_packs: int,
    rng: Random,
) -> list[dict]:
    """Open packs using the real open_premium_pack() and group results per pack."""
    game_state = HeroCardGameState(day=0, coins=0, total_bluestars=0)
    for hero_id in pack.featured_hero_ids:
        hero_def = next((h for h in config.heroes if h.hero_id == hero_id), None)
        if hero_def:
            hero_state = initialize_hero(hero_def)
            for card in hero_state.cards.values():
                card.unlocked = True
            game_state.heroes[hero_id] = hero_state

    card_info: dict[str, dict] = {}
    for hero in config.heroes:
        for card in hero.card_pool:
            card_info[card.card_id] = {
                "name": card.name,
                "hero_name": hero.name,
                "rarity": card.rarity.value,
            }

    packs_results: list[dict] = []
    for pack_idx in range(num_packs):
        pulls = open_premium_pack(pack, game_state, config, rng)
        cards: list[dict] = []
        jokers = 0
        coins = 0
        tokens = 0
        for pull in pulls:
            card_id = pull.get("card_id", "")
            if pull.get("is_joker"):
                jokers += pull.get("joker_count", pull.get("duplicates", 1))
                continue
            rtype = pull.get("reward_type")
            if rtype == "coins":
                coins += pull.get("reward_amount", 0)
                continue
            if rtype == "hero_tokens":
                tokens += pull.get("reward_amount", 0)
                continue
            info = card_info.get(card_id, {})
            rarity = pull.get("rarity") or info.get("rarity", "GRAY")
            entry = {
                "card_id": card_id,
                "card_name": info.get("name", card_id),
                "hero_name": info.get("hero_name", ""),
                "rarity": rarity,
                "duplicates": pull.get("duplicates", 1),
                "pull_kind": pull.get("pull_kind", "main"),
                "pull_since_gold": pull.get("pull_since_gold", 0),
                "post_gold": pull.get("post_gold", False),
                "rarity_weights": pull.get("rarity_weights", {}),
            }
            cards.append(entry)
            # Apply dupes so catch-up weighting works across packs
            for hstate in game_state.heroes.values():
                if card_id in hstate.cards and hstate.cards[card_id].unlocked:
                    hstate.cards[card_id].duplicates += entry["duplicates"]

        packs_results.append({
            "pack_number": pack_idx + 1,
            "cards": cards,
            "jokers": jokers,
            "coins": coins,
            "hero_tokens": tokens,
        })
    return packs_results


def _display(
    packs_results: list[dict],
    pack: PremiumPackDef,
    num_packs: int,
    view_mode: str,
) -> None:
    if not packs_results:
        st.warning("No results.")
        return

    # --- Aggregate metrics ---
    all_cards = [c for p in packs_results for c in p["cards"]]
    total_jokers = sum(p["jokers"] for p in packs_results)
    total_coins = sum(p["coins"] for p in packs_results)
    total_tokens = sum(p["hero_tokens"] for p in packs_results)
    diamonds_spent = num_packs * pack.diamond_cost

    main_cards = [c for c in all_cards if c["pull_kind"] == "main"]
    bonus_cards = [c for c in all_cards if c["pull_kind"] == "bonus"]

    rarity_counts = {r: 0 for r in ("GRAY", "BLUE", "GOLD")}
    rarity_dupes = {r: 0 for r in ("GRAY", "BLUE", "GOLD")}
    for c in all_cards:
        r = c["rarity"]
        rarity_counts[r] = rarity_counts.get(r, 0) + 1
        rarity_dupes[r] = rarity_dupes.get(r, 0) + c["duplicates"]

    st.markdown("---")
    st.subheader("Summary")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Packs opened", num_packs)
    m2.metric("Cards pulled", len(all_cards), help=f"{len(main_cards)} main + {len(bonus_cards)} bonus")
    m3.metric("Diamonds spent", f"{diamonds_spent:,}")
    m4.metric("Cost/pack", f"{pack.diamond_cost:,}")

    r1, r2, r3 = st.columns(3)
    r1.metric("Jokers received", total_jokers, help=f"From {sum(1 for p in packs_results if p['jokers'] > 0)} pack(s)")
    r2.metric("Coins received", f"{total_coins:,}")
    r3.metric("Hero tokens received", f"{total_tokens:,}")

    # --- Per-rarity breakdown ---
    st.markdown("**By rarity**")
    rarity_rows = []
    total = len(all_cards) or 1
    for r in ("GRAY", "BLUE", "GOLD"):
        cnt = rarity_counts.get(r, 0)
        rarity_rows.append({
            "Rarity": r,
            "Pulls": cnt,
            "%": f"{cnt / total * 100:.1f}%",
            "Total dupes": rarity_dupes.get(r, 0),
            "Avg dupes/pull": f"{(rarity_dupes.get(r, 0) / cnt):.1f}" if cnt else "-",
        })
    st.dataframe(pd.DataFrame(rarity_rows), hide_index=True, width="stretch")

    # --- Main vs Bonus breakdown ---
    st.markdown("**Main vs Bonus pulls**")
    mb_rows = []
    for kind, bucket in [("Main", main_cards), ("Bonus", bonus_cards)]:
        cnt = len(bucket)
        by_r = {r: 0 for r in ("GRAY", "BLUE", "GOLD")}
        dupes_by_r = {r: 0 for r in ("GRAY", "BLUE", "GOLD")}
        for c in bucket:
            by_r[c["rarity"]] = by_r.get(c["rarity"], 0) + 1
            dupes_by_r[c["rarity"]] = dupes_by_r.get(c["rarity"], 0) + c["duplicates"]
        mb_rows.append({
            "Bucket": kind,
            "Pulls": cnt,
            "Gray": by_r["GRAY"],
            "Blue": by_r["BLUE"],
            "Gold": by_r["GOLD"],
            "Total dupes": sum(dupes_by_r.values()),
            "Avg dupes/pull": f"{sum(dupes_by_r.values()) / cnt:.1f}" if cnt else "-",
        })
    st.dataframe(pd.DataFrame(mb_rows), hide_index=True, width="stretch")

    if view_mode == "Aggregate only":
        return

    # --- Per-pack detail ---
    st.markdown("---")
    st.subheader("Per-pack detail")
    for pidx, p in enumerate(packs_results):
        # When many packs, collapse all but first three
        expanded = pidx < 3 or num_packs <= 5
        with st.expander(
            f"Pack #{p['pack_number']} -- "
            f"{len(p['cards'])} cards (jokers x{p['jokers']}, coins {p['coins']}, tokens {p['hero_tokens']})",
            expanded=expanded,
        ):
            _render_single_pack(p, pack)


def _render_single_pack(p: dict, pack: PremiumPackDef) -> None:
    """Render one pack with PullSinceUniqueGold counter visible."""
    rows = []
    for idx, c in enumerate(p["cards"]):
        rw = c.get("rarity_weights", {}) or {}
        post = c.get("post_gold", False)
        rows.append({
            "#": idx + 1,
            "Kind": c["pull_kind"].title(),
            "PullSinceGold": c["pull_since_gold"],
            "Phase": "After Gold" if post else f"Pull {c['pull_since_gold']}",
            "Rarity Weights (G/B/Au)": "{:.0f}/{:.0f}/{:.0f}%".format(
                rw.get("GRAY", 0) * 100, rw.get("BLUE", 0) * 100, rw.get("GOLD", 0) * 100,
            ),
            "Rolled": c["rarity"],
            "Card": c["card_name"],
            "Dupes": c["duplicates"],
        })

    df = pd.DataFrame(rows)

    def _style(row):
        color = RARITY_COLORS.get(row["Rolled"], "#444")
        return [f"color: {color}; font-weight: 600" if col == "Rolled" else "" for col in row.index]

    if not df.empty:
        st.dataframe(df.style.apply(_style, axis=1), hide_index=True, width="stretch")

    extras = []
    if p["jokers"]:
        extras.append(f":material/playing_cards: **{p['jokers']}** HeroUniqueJoker (probability {pack.joker_probability*100:.0f}%)")
    if p["coins"]:
        extras.append(f":material/paid: **{p['coins']:,}** coins")
    if p["hero_tokens"]:
        extras.append(f":material/token: **{p['hero_tokens']}** hero tokens")
    if extras:
        st.markdown(" -- ".join(extras))
