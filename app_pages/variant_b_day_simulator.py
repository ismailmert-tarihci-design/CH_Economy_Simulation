"""Day-by-day interactive simulator (Variant B — Hero Card System).

A balancing tool: the user manually advances days, opens daily packs (with
pack-evolution rerolls), claims season pass steps, opens Hero Unique Packs,
and upgrades individual cards. State lives entirely in st.session_state.
"""

from __future__ import annotations

from random import Random
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from simulation.variants.variant_b.models import (
    HeroCardConfig,
    HeroCardGameState,
    PremiumPackDef,
)
from simulation.variants.variant_b import day_simulator as ds
from simulation.variants.variant_b import season_pass as sp
from simulation.variants.variant_b import ftue
from simulation.variants.variant_b.premium_packs import open_premium_pack
from simulation.variants.variant_b.upgrade_engine import (
    attempt_hero_upgrades,
    attempt_shared_upgrades,
)
from simulation.variants.variant_b.hero_deck import (
    get_unlocked_cards,
    hero_card_avg_level,
)


_STATE_KEY = "day_sim"
_MAX_LOG = 80


def _rng() -> Random:
    """Return the persistent RNG. Seed is fixed at start time for reproducibility."""
    return st.session_state[_STATE_KEY]["rng"]


def _log(lines):
    """Append one or more lines to the activity feed (newest first when displayed)."""
    log = st.session_state[_STATE_KEY]["event_log"]
    if isinstance(lines, str):
        log.append(lines)
    else:
        log.extend(lines)
    # Truncate from the front to keep memory bounded
    if len(log) > _MAX_LOG * 2:
        del log[: len(log) - _MAX_LOG]


def _reset(config: HeroCardConfig, seed: Optional[int]) -> None:
    """Mint fresh state for the simulator.

    Day 0 = install day. Only day-0 heroes (Woody) are unlocked; Cowboy and
    later heroes unlock on subsequent days via Next Day.
    """
    rng = Random(seed if seed and seed > 0 else None)
    st.session_state[_STATE_KEY] = {
        "game_state": ds.init_state(config),
        "day": 0,
        "season_pass_step": 1,
        "paid_pass": st.session_state.get(_STATE_KEY, {}).get("paid_pass", False),
        "extras": ds.init_extras(),
        "event_log": [],
        "rng": rng,
        "rng_seed": seed,
        "last_pack_results": [],
        "last_premium_result": None,
        # Per-button lockout for daily packs. Reset on Next Day.
        # Keys: "bundle", "t2", "t1_0", "t1_1", "t1_2"
        "daily_used": set(),
    }
    _log([f"Day 0 (install day) — fresh simulation (seed={seed or 'random'})"])
    # Auto-play the scripted FTUE on D0 (per design: D0 finishes the FTUE and starts playing)
    state = st.session_state[_STATE_KEY]
    ftue_lines = ftue.run_ftue(state["game_state"], config, state["extras"])
    _log(ftue_lines)


def render_variant_b_day_simulator() -> None:
    st.title("Day-by-day simulator (Hero Card System)")
    st.caption(
        "Manual, step-by-step simulator for Variant B. Open daily packs (with "
        "pack-evolution rerolls), advance season pass steps, open Hero Unique Packs, "
        "and upgrade cards one at a time."
    )

    variant_id = st.session_state.get("active_variant", "variant_a")
    if variant_id != "variant_b":
        st.info("Switch to **Hero Card System** variant in the sidebar to use this tool.")
        return

    config: Optional[HeroCardConfig] = st.session_state.configs.get("variant_b")
    if config is None:
        st.warning("No Variant B config loaded.")
        return

    # ─── Top controls ─────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
    with c1:
        seed = st.number_input("Seed (0 = random)", min_value=0, max_value=999999, value=0, key="day_sim_seed")
    with c2:
        if st.button("Start / Reset", type="primary", key="day_sim_reset"):
            _reset(config, int(seed) if seed else None)
            st.rerun()
    with c3:
        if _STATE_KEY in st.session_state:
            st.session_state[_STATE_KEY]["paid_pass"] = st.toggle(
                "Paid season pass",
                value=st.session_state[_STATE_KEY].get("paid_pass", False),
                key="day_sim_paid_toggle",
            )
    with c4:
        if _STATE_KEY in st.session_state:
            sub1, sub2 = st.columns([1, 1])
            with sub1:
                st.metric("Day", st.session_state[_STATE_KEY]["day"])
            with sub2:
                if st.button("Next day →", key="day_sim_next_day"):
                    state = st.session_state[_STATE_KEY]
                    state["day"] += 1
                    unlocks = ds.advance_day(state["game_state"], state["day"], config)
                    state["daily_used"] = set()  # reset daily-pack lockout
                    _log([f"-- Advanced to day {state['day']} --"] + unlocks)
                    st.rerun()

    if _STATE_KEY not in st.session_state:
        st.info("Click **Start / Reset** to begin a new simulation.")
        return

    state = st.session_state[_STATE_KEY]
    game_state: HeroCardGameState = state["game_state"]
    extras: Dict[str, Any] = state["extras"]

    st.markdown("---")

    _render_balances(game_state, extras)
    st.markdown("---")
    _render_heroes_panel(game_state)
    st.markdown("---")
    _render_daily_packs(config, game_state)
    st.markdown("---")
    _render_season_pass(config, game_state)
    st.markdown("---")
    _render_unopened_packs(config, game_state)
    st.markdown("---")
    _render_hero_unique_pack(config, game_state)
    st.markdown("---")
    _render_upgrades(config, game_state)
    st.markdown("---")
    _render_activity_log()


# ─── Balances & inventory ────────────────────────────────────────────────────

def _render_balances(game_state: HeroCardGameState, extras: Dict[str, Any]) -> None:
    st.subheader("Balances & inventory")
    total_unopened = sum(extras["unopened_packs"].values())
    bi = game_state.bonus_items
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Coins", f"{game_state.coins:,}")
    m2.metric("Bluestars", f"{game_state.total_bluestars:,}")
    m3.metric("Hero Tokens", f"{bi.get('HeroTokens', 0):,}")
    m4.metric("Diamonds", f"{bi.get('Diamonds', 0):,}")
    m5.metric("PurpleStars", f"{bi.get('PurpleStars', 0):,}")
    m6.metric("Unopened packs", total_unopened)

    with st.expander("Other resources"):
        rows = [
            {"Resource": "S-Stone",      "Amount": bi.get("S-Stone", 0)},
            {"Resource": "SpiritStone",  "Amount": bi.get("SpiritStone", 0)},
            {"Resource": "RandomDesign", "Amount": bi.get("RandomDesign", 0)},
            {"Resource": "RandomGear",   "Amount": bi.get("RandomGear", 0)},
            {"Resource": "PetFood",      "Amount": bi.get("PetFood", 0)},
            {"Resource": "PetEgg",       "Amount": bi.get("PetEgg", 0)},
            {"Resource": "Everstone",    "Amount": bi.get("Everstone", 0)},
        ]
        misc = extras.get("misc") or {}
        for k, v in misc.items():
            rows.append({"Resource": f"(misc) {k}", "Amount": v})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def _render_heroes_panel(game_state: HeroCardGameState) -> None:
    st.subheader("Heroes")
    if not game_state.heroes:
        st.caption("No heroes unlocked yet.")
        return
    rows = []
    for hero_id, hs in game_state.heroes.items():
        unlocked = get_unlocked_cards(hs)
        rows.append({
            "Hero": hero_id,
            "Level": hs.level,
            "XP": hs.xp,
            "Jokers": hs.joker_count,
            "Unlocked cards": len(unlocked),
            "Avg card level": round(hero_card_avg_level(hs), 2),
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


# ─── Daily packs (1xT2 + 3xT1, each evolves) ─────────────────────────────────

def _render_daily_packs(config: HeroCardConfig, game_state: HeroCardGameState) -> None:
    st.subheader("Daily packs (1× T2 + 3× T1, evolution applies)")
    st.caption("Each button is consumed on click and re-enables on Next Day. The bundle button consumes all 4.")
    bcol1, bcol2, bcol3, bcol4, bcol5 = st.columns(5)
    state = st.session_state[_STATE_KEY]
    used = state.setdefault("daily_used", set())
    all_keys = {"bundle", "t2", "t1_0", "t1_1", "t1_2"}
    bundle_disabled = "bundle" in used or used >= all_keys

    if bcol1.button("Open daily bundle", type="primary", disabled=bundle_disabled, key="day_sim_open_bundle"):
        results = ds.open_daily_bundle(game_state, config, _rng())
        state["last_pack_results"] = results
        _log_pack_results(results)
        used.update(all_keys)
        st.rerun()
    # Per-pack one-at-a-time
    if bcol2.button("Open 1× T2", disabled="t2" in used, key="day_sim_open_t2"):
        r = ds.open_pack_by_name("StandardPackT2", game_state, config, _rng(), apply_evolution=True)
        state["last_pack_results"] = [r]
        _log_pack_results([r])
        used.add("t2")
        st.rerun()
    for i, label in enumerate(("T1 (#1)", "T1 (#2)", "T1 (#3)")):
        key = f"t1_{i}"
        if [bcol3, bcol4, bcol5][i].button(f"Open {label}", disabled=key in used, key=f"day_sim_open_{key}"):
            r = ds.open_pack_by_name("StandardPackT1", game_state, config, _rng(), apply_evolution=True)
            state["last_pack_results"] = [r]
            _log_pack_results([r])
            used.add(key)
            st.rerun()

    _render_pack_results(state.get("last_pack_results") or [])


def _log_pack_results(results: List[Dict[str, Any]]) -> None:
    for r in results:
        start = r.get("start_tier")
        final = r.get("final_tier")
        n = len(r["cards"])
        evo = f" (evolved {start} → {final})" if start and start != final else f" ({final})"
        bonus_summary = ""
        bonuses = r.get("bonus_items") or {}
        if bonuses:
            bonus_summary = " | bonuses: " + ", ".join(f"+{amt} {name}" for name, amt in bonuses.items())
        boost = r.get("unique_boost", 0.0) or r.get("shared_boost", 0.0) or 0.0
        boost_note = f" (dupe boost +{int(boost*100)}%)" if boost else ""
        _log(
            f"Opened pack{evo}: {n} cards, +{r['coins_earned']} coins, "
            f"+{r['jokers_received']} jokers{boost_note}{bonus_summary}"
        )


def _render_pack_results(results: List[Dict[str, Any]]) -> None:
    if not results:
        return
    st.markdown("**Last pack results**")
    for idx, r in enumerate(results):
        start = r.get("start_tier")
        final = r.get("final_tier")
        title = f"Pack #{idx+1}: {final}"
        if start and start != final:
            title = f"Pack #{idx+1}: {start} → {final}"
        with st.expander(f"{title} — {len(r['cards'])} cards, +{r['coins_earned']} coins, +{r['jokers_received']} jokers", expanded=(len(results) <= 2)):
            rows = []
            for c in r["cards"]:
                if c["kind"] == "hero":
                    rows.append({
                        "Kind": "Hero",
                        "Owner": c["hero_id"],
                        "Card": c["card_name"],
                        "Rarity": c["rarity"],
                        "Lvl before": c["level_before"],
                        "Dupes": c["duplicates_received"],
                        "Coins": c["coins_earned"],
                    })
                else:
                    rows.append({
                        "Kind": "Shared",
                        "Owner": c["category"],
                        "Card": c["card_name"],
                        "Rarity": "-",
                        "Lvl before": c["level_before"],
                        "Dupes": c["duplicates_received"],
                        "Coins": c["coins_earned"],
                    })
            if rows:
                st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


# ─── Season pass ─────────────────────────────────────────────────────────────

def _render_season_pass(config: HeroCardConfig, game_state: HeroCardGameState) -> None:
    st.subheader("Season pass")
    state = st.session_state[_STATE_KEY]
    extras = state["extras"]
    next_step = state["season_pass_step"]  # 1-indexed next step to claim
    paid = state["paid_pass"]
    total = len(sp.SEASON_PASS_TABLE)
    claimed = next_step - 1

    # Top summary row
    m1, m2, m3 = st.columns([1, 1, 2])
    m1.metric("Steps claimed", f"{claimed} / {total}")
    m2.metric("Pass track", "Paid (Free + Paid)" if paid else "Free only")
    with m3:
        if next_step <= total:
            target = st.number_input(
                "Claim through step",
                min_value=next_step,
                max_value=total,
                value=min(next_step, total),
                key="day_sim_pass_target",
            )
            if st.button(f"Claim {target - next_step + 1} step(s) (steps {next_step}–{target})",
                         type="primary", key="day_sim_pass_claim"):
                log_lines: List[str] = []
                applied = 0
                while state["season_pass_step"] <= int(target):
                    ok, lines = sp.apply_season_pass_step(state["season_pass_step"], paid, game_state, extras)
                    if not ok:
                        break
                    log_lines.extend(lines)
                    state["season_pass_step"] += 1
                    applied += 1
                _log([f"Claimed {applied} season pass step(s):"] + log_lines)
                st.rerun()
        else:
            st.success("All season pass steps claimed.")

    # Full table of all steps
    rows = []
    for step in sp.SEASON_PASS_TABLE:
        if step.step < next_step:
            status = "✔ claimed"
        elif step.step == next_step:
            status = "→ next"
        else:
            status = ""
        rows.append({
            "#": step.step,
            "Status": status,
            "PurpleStar req": step.required_purple_star,
            "Free": f"{step.free.amount}× {step.free.reward_type}",
            "Paid": f"{step.paid.amount}× {step.paid.reward_type}",
        })
    df = pd.DataFrame(rows)
    # Scrollable view; default height shows ~12 rows
    st.dataframe(df, hide_index=True, width="stretch", height=420)


# ─── Unopened packs inventory ────────────────────────────────────────────────

def _render_unopened_packs(config: HeroCardConfig, game_state: HeroCardGameState) -> None:
    st.subheader("Unopened packs inventory")
    state = st.session_state[_STATE_KEY]
    extras = state["extras"]
    packs = extras["unopened_packs"]
    nonempty = {name: cnt for name, cnt in packs.items() if cnt > 0}
    if not nonempty:
        st.caption("No unopened packs.")
        return

    for name, cnt in sorted(nonempty.items()):
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            st.markdown(f"**{name}**  x {cnt}")
        with c2:
            if st.button("Open one", key=f"day_sim_open_inv_one_{name}"):
                # Inventory packs open without evolution
                r = ds.open_pack_by_name(name, game_state, config, _rng(), apply_evolution=False)
                packs[name] -= 1
                state["last_pack_results"] = [r]
                _log_pack_results([r])
                st.rerun()
        with c3:
            if st.button(f"Open all {cnt}", key=f"day_sim_open_inv_all_{name}"):
                results = []
                while packs[name] > 0:
                    results.append(ds.open_pack_by_name(name, game_state, config, _rng(), apply_evolution=False))
                    packs[name] -= 1
                state["last_pack_results"] = results
                _log_pack_results(results)
                st.rerun()


# ─── Hero Unique Pack (premium per-hero) ─────────────────────────────────────

def _render_hero_unique_pack(config: HeroCardConfig, game_state: HeroCardGameState) -> None:
    st.subheader("Hero Unique Pack (premium, per-hero)")
    if not config.premium_packs:
        st.caption("No premium packs configured.")
        return

    state = st.session_state[_STATE_KEY]
    extras = state["extras"]

    hero_packs: Dict[str, PremiumPackDef] = {p.pack_id: p for p in config.premium_packs}
    hero_names: Dict[str, str] = {h.hero_id: h.name for h in config.heroes if h.hero_id in hero_packs}
    if not hero_names:
        st.caption("No hero packs available for unlocked heroes.")
        return

    c1, c2 = st.columns([2, 1])
    with c1:
        selected_hero = st.selectbox(
            "Hero",
            options=list(hero_names.keys()),
            format_func=lambda x: hero_names[x],
            key="day_sim_hero_pack_select",
        )
    pack = hero_packs[selected_hero]
    with c2:
        if st.button("Open Hero Unique Pack", type="primary", key="day_sim_open_premium"):
            # Ensure hero exists in state with cards unlocked enough to receive drops
            if selected_hero not in game_state.heroes:
                from simulation.variants.variant_b.hero_deck import initialize_hero
                hero_def = next((h for h in config.heroes if h.hero_id == selected_hero), None)
                if hero_def:
                    game_state.heroes[selected_hero] = initialize_hero(hero_def)
            pulls = open_premium_pack(pack, game_state, config, _rng())
            # Apply pulls to game state (mirrors orchestrator logic)
            cards_added = 0
            jokers_added = 0
            coins_added = 0
            tokens_added = 0
            for pull in pulls:
                rtype = pull.get("reward_type")
                if rtype == "coins":
                    amt = pull.get("reward_amount", 0)
                    game_state.coins += amt
                    coins_added += amt
                    continue
                if rtype == "hero_tokens":
                    amt = pull.get("reward_amount", 0)
                    game_state.bonus_items["HeroTokens"] = game_state.bonus_items.get("HeroTokens", 0) + amt
                    tokens_added += amt
                    continue
                if rtype == "bluestars":
                    game_state.total_bluestars += pull.get("reward_amount", 0)
                    continue
                if rtype:
                    continue
                if pull.get("is_joker"):
                    hero_id = pull["hero_id"]
                    if hero_id in game_state.heroes:
                        from simulation.variants.variant_b.hero_joker import add_jokers
                        add_jokers(game_state.heroes[hero_id], 1)
                        jokers_added += 1
                else:
                    hero_id = pull["hero_id"]
                    card_id = pull["card_id"]
                    if hero_id in game_state.heroes:
                        hs = game_state.heroes[hero_id]
                        if card_id in hs.cards and hs.cards[card_id].unlocked:
                            hs.cards[card_id].duplicates += pull["duplicates"]
                            cards_added += 1
            state["last_premium_result"] = {
                "pack_name": pack.name,
                "pulls": pulls,
                "cards_added": cards_added,
                "jokers_added": jokers_added,
                "coins_added": coins_added,
                "tokens_added": tokens_added,
            }
            _log([
                f"Opened {pack.name} (free): "
                f"+{cards_added} cards, +{jokers_added} jokers, +{coins_added} coins, +{tokens_added} tokens"
            ])
            st.rerun()

    last = state.get("last_premium_result")
    if last:
        with st.expander(f"Last opened: {last['pack_name']}", expanded=False):
            rows = []
            for pull in last["pulls"]:
                if pull.get("reward_type") or pull.get("is_joker"):
                    continue
                rows.append({
                    "Kind": pull.get("pull_kind", "?"),
                    "Card": pull.get("card_id", ""),
                    "Rarity": pull.get("rarity", "?"),
                    "Dupes": pull.get("duplicates", 0),
                    "PullSinceGold": pull.get("pull_since_gold", 0),
                })
            if rows:
                st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
            st.caption(
                f"+{last['cards_added']} cards, +{last['jokers_added']} jokers, "
                f"+{last['coins_added']:,} coins, +{last['tokens_added']:,} hero tokens"
            )


# ─── Upgrades ────────────────────────────────────────────────────────────────

def _render_upgrades(config: HeroCardConfig, game_state: HeroCardGameState) -> None:
    st.subheader("Upgrades")

    bc1, bc2 = st.columns([1, 3])
    with bc1:
        if st.button("Greedy auto-upgrade", key="day_sim_auto_upgrade"):
            hero_events, total_xp, total_bs, tree_acts = attempt_hero_upgrades(game_state, config)
            shared_events, shared_bs = attempt_shared_upgrades(game_state, config)
            tree_count = sum(len(v) for v in tree_acts.values())
            _log([
                f"Auto-upgrade: {len(hero_events)} hero upgrades (+{total_xp} XP, +{total_bs} bluestars), "
                f"{len(shared_events)} shared upgrades (+{shared_bs} bluestars), "
                f"{tree_count} skill tree activations"
            ])
            st.rerun()
    with bc2:
        st.caption("Auto-upgrade spends dupes + coins greedily (lowest-level first), mirroring the daily orchestrator.")

    if not game_state.heroes and not game_state.shared_cards:
        st.caption("Nothing to upgrade yet.")
        return

    tabs = []
    tab_labels = []
    for hero_id in game_state.heroes:
        tab_labels.append(f"Hero: {hero_id}")
    tab_labels.append("Shared")
    tabs = st.tabs(tab_labels)

    hero_ids = list(game_state.heroes.keys())
    for i, hero_id in enumerate(hero_ids):
        with tabs[i]:
            _render_hero_upgrade_table(config, game_state, hero_id)

    with tabs[-1]:
        _render_shared_upgrade_table(config, game_state)


def _get_hero_upgrade_table(config: HeroCardConfig, rarity_value: str):
    for t in config.hero_upgrade_tables:
        if t.rarity.value == rarity_value:
            return t
    return None


def _get_shared_upgrade_table(config: HeroCardConfig, category: str):
    for t in config.shared_upgrade_tables:
        if t.category == category:
            return t
    return None


def _render_hero_upgrade_table(config: HeroCardConfig, game_state: HeroCardGameState, hero_id: str) -> None:
    hs = game_state.heroes[hero_id]
    cards = sorted(get_unlocked_cards(hs), key=lambda c: (c.rarity.value, c.level, c.card_id))
    if not cards:
        st.caption(f"{hero_id} has no unlocked cards.")
        return

    st.markdown(f"**{hero_id}** — level {hs.level}, XP {hs.xp}, jokers {hs.joker_count}")

    header_cols = st.columns([2, 1, 1, 1, 1, 1, 1, 1])
    for col, label in zip(header_cols, ["Card", "Rarity", "Lvl", "Dupes", "Need", "Coins need", "Joker fill", ""]):
        col.markdown(f"**{label}**")

    for card in cards:
        table = _get_hero_upgrade_table(config, card.rarity.value)
        level_idx = card.level - 1
        if not table or level_idx >= len(table.duplicate_costs):
            continue
        dupe_cost = table.duplicate_costs[level_idx]
        coin_cost = table.coin_costs[level_idx]

        joker_fill = max(0, dupe_cost - card.duplicates)
        has_dupes = card.duplicates + hs.joker_count >= dupe_cost
        has_coins = game_state.coins >= coin_cost
        enabled = has_dupes and has_coins

        cols = st.columns([2, 1, 1, 1, 1, 1, 1, 1])
        cols[0].write(card.card_id)
        cols[1].write(card.rarity.value)
        cols[2].write(card.level)
        cols[3].write(card.duplicates)
        cols[4].write(dupe_cost)
        cols[5].write(coin_cost)
        cols[6].write(min(joker_fill, hs.joker_count) if joker_fill else 0)
        with cols[7]:
            if st.button("⬆", key=f"day_sim_up_{hero_id}_{card.card_id}", disabled=not enabled):
                result = ds.upgrade_single_hero_card(game_state, config, hero_id, card.card_id)
                if result:
                    evt, tree_acts = result
                    parts = [
                        f"Upgrade {hero_id}/{card.card_id}: L{evt['old_level']}→L{evt['new_level']} "
                        f"(-{evt['dupes_spent']} dupes, -{evt['jokers_spent']} jokers, -{evt['coins_spent']} coins, "
                        f"+{evt['xp_earned']} XP, +{evt['bluestars_earned']} bluestars)"
                    ]
                    if evt["hero_leveled_up"]:
                        parts.append(f"  {hero_id} leveled up!")
                    if tree_acts:
                        for node_idx, card_ids, perk in tree_acts:
                            parts.append(f"  Skill node {node_idx} unlocked ({len(card_ids)} cards, perk={perk!r})")
                    _log(parts)
                st.rerun()


def _render_shared_upgrade_table(config: HeroCardConfig, game_state: HeroCardGameState) -> None:
    if not game_state.shared_cards:
        st.caption("No shared cards.")
        return

    cards = sorted(game_state.shared_cards, key=lambda c: (str(c.category), c.level, c.id))
    header_cols = st.columns([2, 1, 1, 1, 1, 1, 1])
    for col, label in zip(header_cols, ["Card", "Category", "Lvl", "Dupes", "Need", "Coins need", ""]):
        col.markdown(f"**{label}**")

    for card in cards:
        cat = card.category.value if hasattr(card.category, "value") else str(card.category)
        table = _get_shared_upgrade_table(config, cat)
        level_idx = card.level - 1
        if not table or level_idx >= len(table.duplicate_costs):
            continue
        dupe_cost = table.duplicate_costs[level_idx]
        coin_cost = table.coin_costs[level_idx]
        enabled = card.duplicates >= dupe_cost and game_state.coins >= coin_cost

        cols = st.columns([2, 1, 1, 1, 1, 1, 1])
        cols[0].write(card.id)
        cols[1].write(cat)
        cols[2].write(card.level)
        cols[3].write(card.duplicates)
        cols[4].write(dupe_cost)
        cols[5].write(coin_cost)
        with cols[6]:
            if st.button("⬆", key=f"day_sim_up_shared_{card.id}", disabled=not enabled):
                evt = ds.upgrade_single_shared_card(game_state, config, card.id)
                if evt:
                    _log(
                        f"Upgrade {card.id} ({cat}): L{evt['old_level']}→L{evt['new_level']} "
                        f"(-{evt['dupes_spent']} dupes, -{evt['coins_spent']} coins, +{evt['bluestars_earned']} bluestars)"
                    )
                st.rerun()


# ─── Activity log ────────────────────────────────────────────────────────────

def _render_activity_log() -> None:
    st.subheader("Activity log")
    log: List[str] = st.session_state[_STATE_KEY]["event_log"]
    if not log:
        st.caption("No activity yet.")
        return
    shown = log[-_MAX_LOG:][::-1]
    st.text("\n".join(shown))
