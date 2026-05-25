"""Day-by-day interactive simulator (Variant B — Hero Card System).

A balancing tool: the user manually advances days, opens daily packs (with
pack-evolution rerolls), claims season pass steps (rewards apply
immediately — pack rewards auto-open), opens Hero Unique Packs, and
upgrades individual cards. State lives entirely in st.session_state.
"""

from __future__ import annotations

import json
from pathlib import Path
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
from simulation.variants.variant_b.skill_tree import check_and_advance_skill_tree
from simulation.variants.variant_b.scripted_run import (
    ScriptedRunConfig,
    ScriptedRunDay,
    delete_scripted_run,
    list_scripted_runs,
    load_scripted_run,
    save_scripted_run,
)
from simulation.variants.variant_b.scripted_runner import run_one_day as scripted_run_one_day
from simulation.variants.variant_b.chapter_schedule import (
    chapters_for_sim_day as _chapters_for_sim_day,
    load_cohort_chapters as _load_cohort_chapters,
)


_STATE_KEY = "day_sim"
_MAX_LOG = 120


def _snapshot_history(state: Dict[str, Any]) -> None:
    """Capture a per-day snapshot for the history charts."""
    game_state: HeroCardGameState = state["game_state"]
    snap = {
        "day": state["day"],
        "bluestars": game_state.total_bluestars,
        "coins": game_state.coins,
        "heroes": {
            hero_id: {
                "level": hs.level,
                "xp": hs.xp,
                "jokers": hs.joker_count,
                "unlocked_cards": len(get_unlocked_cards(hs)),
                "avg_card_level": hero_card_avg_level(hs),
            }
            for hero_id, hs in game_state.heroes.items()
        },
    }
    history = state.setdefault("history", [])
    # Replace if we already have a snapshot for this day (FTUE / reset cases).
    if history and history[-1]["day"] == state["day"]:
        history[-1] = snap
    else:
        history.append(snap)


def _hero_def(config: HeroCardConfig, hero_id: str):
    return next((h for h in config.heroes if h.hero_id == hero_id), None)


def _xp_to_next_level(hero_def, hero_level: int) -> int:
    """Return the XP threshold needed to reach the next level, or 0 if maxed."""
    if hero_def is None or hero_level >= hero_def.max_level:
        return 0
    idx = hero_level - 1
    if idx < 0 or idx >= len(hero_def.xp_per_level):
        return 0
    return hero_def.xp_per_level[idx]


# ─── State helpers ───────────────────────────────────────────────────────────

def _rng() -> Random:
    return st.session_state[_STATE_KEY]["rng"]


def _log(lines):
    log = st.session_state[_STATE_KEY]["event_log"]
    if isinstance(lines, str):
        log.append(lines)
    else:
        log.extend(lines)
    if len(log) > _MAX_LOG * 2:
        del log[: len(log) - _MAX_LOG]


# ─── Player-cohort chapter cadence ───────────────────────────────────────────
#
# The chapter-completion rhythm comes from the chosen player cohort profile
# (Average / P75 / P90) — same data that drives the daily pack schedule.
# Each profile JSON ships a 26-day `chapters_per_day: list[int]` field (CSV
# day 0 → simulator day 1). When the user presses "Next day", we auto-beat
# that many chapters before advancing, so manual stepping mirrors the
# scripted Monte Carlo behaviour.

_COHORT_PROFILES = ["Average", "P75", "P90"]
_DEFAULT_COHORT = "Average"


# `_load_cohort_chapters` and `_chapters_for_sim_day` now live in
# `simulation.variants.variant_b.chapter_schedule` (shared with the big
# orchestrator). They are re-imported above so the existing call sites keep
# working with the same private-looking names.


def _auto_beat_chapters(state: Dict[str, Any], config: HeroCardConfig, n: int) -> None:
    """Beat `n` chapters: open n EndOfChapter packs, update counters, log."""
    if n <= 0:
        return
    last_results: List[Dict[str, Any]] = []
    for _ in range(n):
        r = ds.open_pack_by_name(
            "EndOfChapterPack", state["game_state"], config, _rng(), apply_evolution=False
        )
        last_results.append(r)
    state["chapters_beaten"] = state.get("chapters_beaten", 0) + n
    state["last_pack_results"] = last_results
    _log([f"Auto-beat {n} chapter(s) on day {state['day']} → {n} EndOfChapter pack(s) opened"])
    _log_pack_results(last_results)


def _reset(config: HeroCardConfig, seed: Optional[int]) -> None:
    rng = Random(seed if seed and seed > 0 else None)
    prev = st.session_state.get(_STATE_KEY, {})
    paid_pass = prev.get("paid_pass", False)
    cohort = prev.get("cohort") or _DEFAULT_COHORT
    chapters_per_day = _load_cohort_chapters(cohort)
    st.session_state[_STATE_KEY] = {
        "game_state": ds.init_state(config),
        "day": 0,
        "season_pass_step": 1,
        "paid_pass": paid_pass,
        "extras": ds.init_extras(),
        "event_log": [],
        "rng": rng,
        "rng_seed": seed,
        "last_pack_results": [],
        "last_premium_result": None,
        "daily_used": set(),
        "chapters_beaten": 0,
        "cohort": cohort,
        "chapters_per_day": chapters_per_day,
    }
    _log([f"Day 0 (install day) — fresh simulation (seed={seed or 'random'})"])
    state = st.session_state[_STATE_KEY]
    state["history"] = []
    ftue_lines = ftue.run_ftue(state["game_state"], config, state["extras"])
    _log(ftue_lines)

    # FTUE pack steps already opened the SP1, SP2, SP4 packs and credited
    # their cards. Catch the season-pass tracker up through step 4 and apply
    # only the non-pack rewards (e.g. SP step 3 diamonds), skipping packs to
    # avoid double-crediting.
    catchup_lines: List[str] = ["── Pre-claiming SP steps 1–4 (packs already opened in FTUE) ──"]
    for sp_step in range(1, 5):
        ok, lines, _opened = sp.apply_season_pass_step(
            sp_step, paid_pass, state["game_state"], state["extras"],
            config=config, rng=rng, skip_packs=True,
        )
        if ok:
            catchup_lines.extend(lines)
    state["season_pass_step"] = 5
    _log(catchup_lines)

    _snapshot_history(state)


# ─── Top-level render ────────────────────────────────────────────────────────

def render_variant_b_day_simulator() -> None:
    st.title("Day-by-day simulator")
    st.caption(
        "Manual, step-by-step Variant B simulator. Open daily packs (with "
        "evolution rerolls), claim season-pass steps (packs auto-open), open "
        "Hero Unique Packs, and upgrade cards one at a time."
    )

    variant_id = st.session_state.get("active_variant", "variant_a")
    if variant_id != "variant_b":
        st.info("Switch to **Hero Card System** variant in the sidebar to use this tool.")
        return

    config: Optional[HeroCardConfig] = st.session_state.configs.get("variant_b")
    if config is None:
        st.warning("No Variant B config loaded.")
        return

    _render_top_bar(config)

    if _STATE_KEY not in st.session_state:
        st.info("Click **Start / Reset** above to begin a new simulation.")
        return

    state = st.session_state[_STATE_KEY]
    game_state: HeroCardGameState = state["game_state"]

    _render_balances(game_state)
    _render_heroes_panel(config, game_state)

    tab_manual, tab_scenario = st.tabs(["🎮 Manual Play", "🤖 Scenario Play"])
    with tab_manual:
        sub_packs, sub_pass, sub_hero_pack, sub_upgrades = st.tabs(
            ["🎴 Daily Packs", "🏆 Season Pass", "⭐ Hero Pack", "⚒ Upgrades"]
        )
        with sub_packs:
            _render_daily_packs(config, game_state)
        with sub_pass:
            _render_season_pass(config, game_state)
        with sub_hero_pack:
            _render_hero_unique_pack(config, game_state)
        with sub_upgrades:
            _render_upgrades(config, game_state)
    with tab_scenario:
        _render_scripted_run(config, game_state)

    # Charts + activity log are useful across both modes — render below the
    # mode tabs as collapsible sections so they're always reachable.
    with st.expander("📈 Charts", expanded=False):
        _render_charts(config, game_state)
    with st.expander("📜 Activity Log", expanded=False):
        _render_activity_log()


# ─── Sticky top bar ──────────────────────────────────────────────────────────

def _render_top_bar(config: HeroCardConfig) -> None:
    with st.container(border=True):
        c_seed, c_reset, c_cohort, c_paid, c_day, c_chap, c_next = st.columns(
            [1.0, 1.0, 1.1, 1.2, 0.7, 0.9, 1.2]
        )
        with c_seed:
            seed = st.number_input(
                "Seed (0 = random)", min_value=0, max_value=999999, value=0, key="day_sim_seed"
            )
        with c_reset:
            st.write("")  # vertical alignment
            if st.button("🔄 Start / Reset", type="primary", key="day_sim_reset", width="stretch"):
                _reset(config, int(seed) if seed else None)
                st.rerun()
        with c_cohort:
            current_cohort = (
                st.session_state.get(_STATE_KEY, {}).get("cohort")
                or _DEFAULT_COHORT
            )
            picked_cohort = st.selectbox(
                "Player cohort",
                options=_COHORT_PROFILES,
                index=_COHORT_PROFILES.index(current_cohort)
                    if current_cohort in _COHORT_PROFILES else 0,
                key="day_sim_cohort",
                help="Drives chapters-per-day on 'Next day'. Source: matching profile JSON.",
            )
            if _STATE_KEY in st.session_state and picked_cohort != current_cohort:
                st.session_state[_STATE_KEY]["cohort"] = picked_cohort
                st.session_state[_STATE_KEY]["chapters_per_day"] = _load_cohort_chapters(picked_cohort)
                _log([f"Cohort switched to **{picked_cohort}** — chapters-per-day reloaded."])
        with c_paid:
            st.write("")
            if _STATE_KEY in st.session_state:
                st.session_state[_STATE_KEY]["paid_pass"] = st.toggle(
                    "💎 Paid season pass",
                    value=st.session_state[_STATE_KEY].get("paid_pass", False),
                    key="day_sim_paid_toggle",
                )
        with c_day:
            if _STATE_KEY in st.session_state:
                st.metric("Day", st.session_state[_STATE_KEY]["day"])
        with c_chap:
            if _STATE_KEY in st.session_state:
                st.metric(
                    "Chapters",
                    st.session_state[_STATE_KEY].get("chapters_beaten", 0),
                )
        with c_next:
            st.write("")
            if _STATE_KEY in st.session_state:
                if st.button("Next day →", key="day_sim_next_day", type="secondary", width="stretch"):
                    state = st.session_state[_STATE_KEY]
                    # Snapshot the *current* (about-to-end) day before advancing.
                    _snapshot_history(state)
                    state["day"] += 1
                    unlocks = ds.advance_day(state["game_state"], state["day"], config)
                    state["daily_used"] = set()
                    _log([f"── Advanced to day {state['day']} ──"] + unlocks)
                    # Auto-beat the cohort's chapters for this new day. This
                    # is what makes manual play mirror scripted Monte Carlo
                    # behaviour: the chapter rhythm comes from the chosen
                    # player cohort instead of relying on the user to click
                    # the "Beat chapter" button N times.
                    chapters_today = _chapters_for_sim_day(
                        state.get("chapters_per_day", []), state["day"]
                    )
                    _auto_beat_chapters(state, config, chapters_today)
                    _snapshot_history(state)
                    st.rerun()


# ─── Balances ────────────────────────────────────────────────────────────────

def _render_balances(game_state: HeroCardGameState) -> None:
    bi = game_state.bonus_items
    with st.container(border=True):
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("🪙 Coins", f"{game_state.coins:,}")
        m2.metric("⭐ Bluestars", f"{game_state.total_bluestars:,}")
        m3.metric("🎟 Hero Tokens", f"{bi.get('HeroTokens', 0):,}")
        m4.metric("💎 Diamonds", f"{bi.get('Diamonds', 0):,}")

        with st.expander("Other resources", expanded=False):
            rows = [
                {"Resource": "RandomDesign", "Amount": bi.get("RandomDesign", 0)},
                {"Resource": "RandomGear",   "Amount": bi.get("RandomGear", 0)},
                {"Resource": "PetFood",      "Amount": bi.get("PetFood", 0)},
                {"Resource": "PetEgg",       "Amount": bi.get("PetEgg", 0)},
                {"Resource": "Everstone",    "Amount": bi.get("Everstone", 0)},
            ]
            misc = st.session_state[_STATE_KEY]["extras"].get("misc") or {}
            for k, v in misc.items():
                if k in ("SpiritStone", "S-Stone"):
                    continue
                rows.append({"Resource": f"(misc) {k}", "Amount": v})
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def _render_heroes_panel(config: HeroCardConfig, game_state: HeroCardGameState) -> None:
    if not game_state.heroes:
        return
    with st.container(border=True):
        st.markdown("**Hero state**")
        st.caption(
            "Per-hero level, XP-to-next, jokers, and card-level breakdown by rarity. "
            "Use the selector to focus on a subset of heroes."
        )

        hero_ids = list(game_state.heroes.keys())
        name_by_id = {hid: (_hero_def(config, hid).name if _hero_def(config, hid) else hid)
                      for hid in hero_ids}

        default_pick = st.session_state.get("day_sim_hero_pick")
        if not default_pick:
            default_pick = hero_ids
        # Drop any selections that no longer exist
        default_pick = [h for h in default_pick if h in hero_ids]

        picked = st.multiselect(
            "Heroes to show",
            options=hero_ids,
            default=default_pick,
            format_func=lambda hid: name_by_id.get(hid, hid),
            key="day_sim_hero_pick",
        )
        if not picked:
            st.caption("No heroes selected.")
            return

        rows: List[Dict[str, Any]] = []
        for hid in picked:
            hs = game_state.heroes[hid]
            hero_def = _hero_def(config, hid)
            max_lvl = hero_def.max_level if hero_def else 50
            needed = _xp_to_next_level(hero_def, hs.level)
            cards = list(hs.cards.values())
            unlocked = [c for c in cards if c.unlocked]
            locked_count = len(cards) - len(unlocked)

            pool_by_rarity: Dict[str, int] = {"GRAY": 0, "BLUE": 0, "GOLD": 0}
            unl_by_rarity: Dict[str, List[Any]] = {"GRAY": [], "BLUE": [], "GOLD": []}
            for c in cards:
                pool_by_rarity[c.rarity.value] = pool_by_rarity.get(c.rarity.value, 0) + 1
            for c in unlocked:
                unl_by_rarity.setdefault(c.rarity.value, []).append(c)

            def _rarity_cell(r: str) -> str:
                u = len(unl_by_rarity.get(r, []))
                t = pool_by_rarity.get(r, 0)
                if u == 0:
                    return f"0 / {t}"
                avg_lvl = sum(c.level for c in unl_by_rarity[r]) / u
                return f"{u} / {t} · avg L{avg_lvl:.1f}"

            rows.append({
                "Hero": name_by_id.get(hid, hid),
                "Level": f"{hs.level} / {max_lvl}",
                "XP → next": (f"{hs.xp:,} / {needed:,} ({(hs.xp / needed * 100):.0f}%)"
                              if needed > 0 else "MAX"),
                "Jokers": hs.joker_count,
                "Cards unlocked": f"{len(unlocked)} / {len(cards)}",
                "Avg card lvl": round(hero_card_avg_level(hs), 2),
                "GRAY": _rarity_cell("GRAY"),
                "BLUE": _rarity_cell("BLUE"),
                "GOLD": _rarity_cell("GOLD"),
                "Locked": locked_count,
            })

        st.dataframe(
            pd.DataFrame(rows),
            hide_index=True,
            width="stretch",
            height=min(560, 80 + 36 * len(rows)),
        )

        # Per-hero pet & gear progression (Task 4). Each hero owns its own
        # pet level + gear slot levels; PetPacks/GearPacks credit the
        # most-recently-unlocked hero.
        with st.expander("Pet & gear (per hero)", expanded=False):
            pg_rows: List[Dict[str, Any]] = []
            for hid in picked:
                hs = game_state.heroes[hid]
                slot_pairs = ", ".join(
                    f"{slot}: L{lvl}" for slot, lvl in sorted(hs.gear.slot_levels.items())
                )
                pg_rows.append({
                    "Hero": name_by_id.get(hid, hid),
                    "Pet level": hs.pet.level,
                    "Pet XP": hs.pet.xp,
                    "Pet packs opened": hs.pet.pet_packs_opened,
                    "Gear total level": sum(hs.gear.slot_levels.values()),
                    "Gear slots": slot_pairs,
                    "Gear packs opened": hs.gear.gear_packs_opened,
                })
            st.dataframe(
                pd.DataFrame(pg_rows),
                hide_index=True,
                width="stretch",
                height=min(360, 80 + 36 * len(pg_rows)),
            )
            target = game_state.last_unlocked_hero
            if target:
                target_name = name_by_id.get(target, target)
                st.caption(
                    f"PetPack / GearPack opens credit **{target_name}** (most recently unlocked hero)."
                )

        # Optional card-level drill-down for one of the picked heroes
        with st.expander("Card-level detail (pick one hero)", expanded=False):
            drill_hid = st.selectbox(
                "Hero",
                options=picked,
                format_func=lambda hid: name_by_id.get(hid, hid),
                key="day_sim_hero_drill",
            )
            hs = game_state.heroes[drill_hid]
            unlocked = [c for c in hs.cards.values() if c.unlocked]
            if unlocked:
                detail_rows = [
                    {"Card": c.card_id, "Rarity": c.rarity.value, "Level": c.level, "Dupes": c.duplicates}
                    for c in sorted(unlocked, key=lambda x: (x.rarity.value, -x.level, x.card_id))
                ]
                st.dataframe(pd.DataFrame(detail_rows), hide_index=True, width="stretch", height=280)
            else:
                st.caption("No cards unlocked yet for this hero.")


# ─── Daily packs ─────────────────────────────────────────────────────────────

def _render_daily_packs(config: HeroCardConfig, game_state: HeroCardGameState) -> None:
    state = st.session_state[_STATE_KEY]
    used = state.setdefault("daily_used", set())
    all_keys = {"bundle", "t2", "t1_0", "t1_1", "t1_2"}
    bundle_disabled = "bundle" in used or used >= all_keys

    with st.container(border=True):
        st.markdown("**Daily packs** — 1× T2 + 3× T1, evolution applies")
        st.caption("Each button is consumed on click and re-enables on Next Day.")

        b_bundle, b_t2, b_t1a, b_t1b, b_t1c = st.columns(5)
        if b_bundle.button("🎁 Open daily bundle (all 4)",
                           type="primary", disabled=bundle_disabled,
                           key="day_sim_open_bundle", width="stretch"):
            results = ds.open_daily_bundle(game_state, config, _rng())
            state["last_pack_results"] = results
            _log_pack_results(results)
            used.update(all_keys)
            st.rerun()
        if b_t2.button("Open 1× T2", disabled="t2" in used,
                       key="day_sim_open_t2", width="stretch"):
            r = ds.open_pack_by_name("StandardPackT2", game_state, config, _rng(), apply_evolution=True)
            state["last_pack_results"] = [r]
            _log_pack_results([r])
            used.add("t2")
            st.rerun()
        for i, (col, label) in enumerate(zip([b_t1a, b_t1b, b_t1c], ("T1 #1", "T1 #2", "T1 #3"))):
            key = f"t1_{i}"
            if col.button(f"Open {label}", disabled=key in used,
                          key=f"day_sim_open_{key}", width="stretch"):
                r = ds.open_pack_by_name("StandardPackT1", game_state, config, _rng(), apply_evolution=True)
                state["last_pack_results"] = [r]
                _log_pack_results([r])
                used.add(key)
                st.rerun()

    with st.container(border=True):
        st.markdown("**Story progression**")
        st.caption("Each chapter beaten opens one EndOfChapter pack. No daily cap.")
        b_beat, b_beat_n = st.columns([1.4, 1])
        if b_beat.button(
            "⚔️ Beat chapter (open EndOfChapter pack)",
            type="primary",
            key="day_sim_beat_chapter",
            width="stretch",
        ):
            r = ds.open_pack_by_name(
                "EndOfChapterPack", game_state, config, _rng(), apply_evolution=False
            )
            state["last_pack_results"] = [r]
            state["chapters_beaten"] = state.get("chapters_beaten", 0) + 1
            _log([f"Beat chapter #{state['chapters_beaten']} → EndOfChapter pack opened"])
            _log_pack_results([r])
            st.rerun()
        with b_beat_n:
            st.caption(f"Total chapters beaten: **{state.get('chapters_beaten', 0)}**")

    _render_pack_results(state.get("last_pack_results") or [], header="Last pack results")


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


def _render_pack_results(results: List[Dict[str, Any]], header: str = "Pack results") -> None:
    if not results:
        return
    with st.container(border=True):
        st.markdown(f"**{header}** ({len(results)} pack(s))")
        # Summary metrics across all results
        total_cards = sum(len(r["cards"]) for r in results)
        total_coins = sum(r["coins_earned"] for r in results)
        total_jokers = sum(r["jokers_received"] for r in results)
        s1, s2, s3 = st.columns(3)
        s1.metric("Cards pulled", total_cards)
        s2.metric("Coins gained", f"{total_coins:,}")
        s3.metric("Jokers gained", total_jokers)

        for idx, r in enumerate(results):
            start = r.get("start_tier")
            final = r.get("final_tier")
            title = f"Pack #{idx+1}: {start} → {final}" if start and start != final else f"Pack #{idx+1}: {final}"
            with st.expander(
                f"{title} — {len(r['cards'])} cards, +{r['coins_earned']} coins, +{r['jokers_received']} jokers",
                expanded=(len(results) <= 2),
            ):
                rows = []
                for c in r["cards"]:
                    base = c.get("dupe_base_cost", 0) or 0
                    eff = c.get("dupe_effective_pct", 0.0) or 0.0
                    raw = c.get("dupe_pct", 0.0) or 0.0
                    boost = c.get("dupe_boost", 0.0) or 0.0
                    pct_label = f"{eff * 100:.1f}%" if base else "—"
                    if boost:
                        pct_label += f" (raw {raw*100:.1f}% +{int(boost*100)}%)"
                    need_label = f"{c['duplicates_received']} / {base}" if base else f"{c['duplicates_received']}"
                    if c["kind"] == "hero":
                        rows.append({
                            "Kind": "Hero", "Owner": c["hero_id"], "Card": c["card_name"],
                            "Rarity": c["rarity"], "Lvl before": c["level_before"],
                            "Dupes/Need": need_label, "% of next lvl": pct_label,
                            "Coins": c["coins_earned"],
                        })
                    else:
                        rows.append({
                            "Kind": "Shared", "Owner": c["category"], "Card": c["card_name"],
                            "Rarity": "—", "Lvl before": c["level_before"],
                            "Dupes/Need": need_label, "% of next lvl": pct_label,
                            "Coins": c["coins_earned"],
                        })
                if rows:
                    st.caption(
                        "**Dupes/Need** = dupes pulled / dupes required to reach next level. "
                        "**% of next lvl** = effective % of next-level cost this single pull covered "
                        "(pack boost applied)."
                    )
                    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
                bonuses = r.get("bonus_items") or {}
                if bonuses:
                    st.caption("Bonus items: " + ", ".join(f"+{amt} {name}" for name, amt in bonuses.items()))


# ─── Season pass ─────────────────────────────────────────────────────────────

def _render_season_pass(config: HeroCardConfig, game_state: HeroCardGameState) -> None:
    state = st.session_state[_STATE_KEY]
    extras = state["extras"]
    next_step = state["season_pass_step"]
    paid = state["paid_pass"]
    total = len(sp.SEASON_PASS_TABLE)
    claimed = next_step - 1

    with st.container(border=True):
        m1, m2, m3 = st.columns([1, 1, 1])
        m1.metric("Steps claimed", f"{claimed} / {total}")
        m2.metric("Track", "Free + Paid" if paid else "Free only")
        m3.progress(min(1.0, claimed / total), text=f"{claimed}/{total} claimed")

        if next_step <= total:
            t1, t2 = st.columns([2, 1])
            with t1:
                target = st.number_input(
                    "Claim through step",
                    min_value=next_step,
                    max_value=total,
                    value=min(next_step, total),
                    key="day_sim_pass_target",
                )
            with t2:
                st.write("")
                if st.button(f"Claim steps {next_step}–{int(target)}",
                             type="primary", key="day_sim_pass_claim", width="stretch"):
                    log_lines: List[str] = []
                    all_opened: List[Dict[str, Any]] = []
                    applied = 0
                    while state["season_pass_step"] <= int(target):
                        ok, lines, opened = sp.apply_season_pass_step(
                            state["season_pass_step"], paid, game_state, extras,
                            config=config, rng=_rng(),
                        )
                        if not ok:
                            break
                        log_lines.extend(lines)
                        all_opened.extend(opened)
                        state["season_pass_step"] += 1
                        applied += 1
                    _log([f"Claimed {applied} season pass step(s):"] + log_lines)
                    if all_opened:
                        _log_pack_results(all_opened)
                        state["last_pack_results"] = all_opened
                    st.rerun()
        else:
            st.success("✓ All season pass steps claimed.")

    # Reward table
    with st.container(border=True):
        st.markdown("**Reward table**")
        rows = []
        for step in sp.SEASON_PASS_TABLE:
            if step.step < next_step:
                status = "✓ claimed"
            elif step.step == next_step:
                status = "→ next"
            else:
                status = ""
            rows.append({
                "#": step.step,
                "Status": status,
                "Free": f"{step.free.amount}× {step.free.reward_type}",
                "Paid": f"{step.paid.amount}× {step.paid.reward_type}",
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", height=420)


# ─── Hero Unique Pack (premium per-hero) ─────────────────────────────────────

def _render_hero_unique_pack(config: HeroCardConfig, game_state: HeroCardGameState) -> None:
    if not config.premium_packs:
        st.caption("No premium packs configured.")
        return

    state = st.session_state[_STATE_KEY]

    hero_packs: Dict[str, PremiumPackDef] = {p.pack_id: p for p in config.premium_packs}
    hero_names: Dict[str, str] = {h.hero_id: h.name for h in config.heroes if h.hero_id in hero_packs}
    if not hero_names:
        st.caption("No hero packs available for unlocked heroes.")
        return

    with st.container(border=True):
        st.markdown("**Hero Unique Pack** — premium, per-hero")
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
            st.write("")
            if st.button("⭐ Open Hero Unique Pack", type="primary",
                         key="day_sim_open_premium", width="stretch"):
                _do_open_premium_pack(pack, selected_hero, config, game_state, state)
                st.rerun()

    last = state.get("last_premium_result")
    if last:
        with st.container(border=True):
            st.markdown(f"**Last opened: {last['pack_name']}**")
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Cards", last["cards_added"])
            s2.metric("Jokers", last["jokers_added"])
            s3.metric("Coins", f"{last['coins_added']:,}")
            s4.metric("Hero tokens", f"{last['tokens_added']:,}")
            with st.expander("Pull detail", expanded=False):
                rows = []
                for pull in last["pulls"]:
                    if pull.get("reward_type") or pull.get("is_joker"):
                        continue
                    base = pull.get("dupe_base_cost", 0) or 0
                    eff = pull.get("dupe_effective_pct", 0.0) or 0.0
                    rows.append({
                        "Kind": pull.get("pull_kind", "?"),
                        "Card": pull.get("card_id", ""),
                        "Rarity": pull.get("rarity", "?"),
                        "Dupes/Need": f"{pull.get('duplicates', 0)} / {base}" if base else f"{pull.get('duplicates', 0)}",
                        "% of next lvl": f"{eff * 100:.1f}%" if base else "—",
                        "PullSinceGold": pull.get("pull_since_gold", 0),
                    })
                if rows:
                    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def _do_open_premium_pack(
    pack: PremiumPackDef, selected_hero: str,
    config: HeroCardConfig, game_state: HeroCardGameState,
    state: Dict[str, Any],
) -> None:
    if selected_hero not in game_state.heroes:
        from simulation.variants.variant_b.hero_deck import initialize_hero
        hero_def = next((h for h in config.heroes if h.hero_id == selected_hero), None)
        if hero_def:
            game_state.heroes[selected_hero] = initialize_hero(hero_def)
    pulls = open_premium_pack(pack, game_state, config, _rng())
    cards_added = jokers_added = coins_added = tokens_added = 0
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


# ─── Upgrades ────────────────────────────────────────────────────────────────

def _render_upgrades(config: HeroCardConfig, game_state: HeroCardGameState) -> None:
    with st.container(border=True):
        bc1, bc2 = st.columns([1, 3])
        with bc1:
            if st.button("⚡ Greedy auto-upgrade", key="day_sim_auto_upgrade", width="stretch"):
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

    if game_state.heroes:
        _render_skill_tree_panel(config, game_state)

    if not game_state.heroes and not game_state.shared_cards:
        st.caption("Nothing to upgrade yet.")
        return

    tab_labels = [f"Hero: {hero_id}" for hero_id in game_state.heroes] + ["Shared"]
    tabs = st.tabs(tab_labels)

    hero_ids = list(game_state.heroes.keys())
    for i, hero_id in enumerate(hero_ids):
        with tabs[i]:
            _render_hero_upgrade_table(config, game_state, hero_id)
    with tabs[-1]:
        _render_shared_upgrade_table(config, game_state)


def _render_skill_tree_panel(config: HeroCardConfig, game_state: HeroCardGameState) -> None:
    """Per-hero skill-tree status + 'buy next node' button.

    The next node activates only when (a) the hero meets its level requirement
    and (b) the player has enough Hero Tokens. Activation debits tokens via
    `check_and_advance_skill_tree`.
    """
    tokens = int(game_state.bonus_items.get("HeroTokens", 0))
    with st.container(border=True):
        st.markdown(f"**Skill tree** — Hero Tokens: **{tokens:,}**")
        st.caption(
            "Each hero progresses through a linear skill tree. The next node "
            "unlocks when the hero meets the level requirement AND the player "
            "can pay its Hero Token cost."
        )

        rows = []
        for hero_id, hs in game_state.heroes.items():
            hero_def = _hero_def(config, hero_id)
            if hero_def is None or not hero_def.skill_tree:
                continue
            next_idx = hs.skill_tree_progress + 1
            if next_idx >= len(hero_def.skill_tree):
                rows.append((hero_id, hero_def.name, None, None, None, None, "MAX"))
                continue
            node = hero_def.skill_tree[next_idx]
            level_ok = hs.level >= node.hero_level_required
            token_ok = tokens >= node.token_cost
            rows.append((
                hero_id, hero_def.name, node, level_ok, token_ok, hs.level,
                None,
            ))

        if not rows:
            st.caption("No heroes with skill trees yet.")
            return

        for hero_id, name, node, level_ok, token_ok, hero_level, status in rows:
            if status == "MAX":
                cols = st.columns([2, 1, 3, 1])
                cols[0].write(f"**{name}**")
                cols[1].write(f"L{hero_level if hero_level is not None else '-'}")
                cols[2].caption("Skill tree complete")
                cols[3].caption("✓")
                continue
            cols = st.columns([2, 1, 3, 1])
            cols[0].write(f"**{name}**")
            cols[1].write(f"L{hero_level} → L{node.hero_level_required}")
            req_bits = []
            if not level_ok:
                req_bits.append(f"needs L{node.hero_level_required}")
            if not token_ok:
                req_bits.append(f"needs {node.token_cost - tokens:,} more tokens")
            req_label = " · ".join(req_bits) if req_bits else "ready"
            cols[2].caption(
                f"Node #{node.node_index} · {node.perk_label or '—'} · "
                f"cost {node.token_cost:,} tokens · {req_label}"
            )
            with cols[3]:
                if st.button(
                    "Buy", key=f"day_sim_buy_node_{hero_id}",
                    disabled=not (level_ok and token_ok),
                ):
                    hero_def = _hero_def(config, hero_id)
                    activated = check_and_advance_skill_tree(
                        hero_def, game_state.heroes[hero_id],
                        game_state.heroes[hero_id].level,
                        bonus_items=game_state.bonus_items,
                    )
                    for node_idx, card_ids, perk in activated:
                        _log([
                            f"Activated skill node #{node_idx} for {name}: "
                            f"perk={perk!r}, unlocked {len(card_ids)} card(s)"
                        ])
                    st.rerun()


_SCRIPTED_KEY = "day_sim_scripted_cfg"


def _ensure_scripted_cfg() -> ScriptedRunConfig:
    """Return the in-memory scripted-run config, creating a blank one if needed."""
    cfg = st.session_state.get(_SCRIPTED_KEY)
    if cfg is None or not isinstance(cfg, ScriptedRunConfig):
        cfg = ScriptedRunConfig(name="untitled", schedule=[])
        st.session_state[_SCRIPTED_KEY] = cfg
    return cfg


def _render_scripted_run(config: HeroCardConfig, game_state: HeroCardGameState) -> None:
    """Auto-pilot mode: each scripted day opens packs, claims season pass, beats
    chapters, and spends Hero Tokens per a saved policy.
    """
    cfg = _ensure_scripted_cfg()

    with st.container(border=True):
        st.markdown("**Scripted-run preset**")
        c_name, c_save, c_delete = st.columns([3, 1, 1])
        with c_name:
            new_name = st.text_input(
                "Preset name", value=cfg.name, key="day_sim_scripted_name",
            )
            cfg.name = new_name.strip() or "untitled"
        with c_save:
            st.write("")
            if st.button("💾 Save preset", key="day_sim_scripted_save", width="stretch"):
                save_scripted_run(cfg)
                st.toast(f"Saved preset '{cfg.name}'")
        with c_delete:
            st.write("")
            if st.button("🗑 Delete", key="day_sim_scripted_delete", width="stretch"):
                if delete_scripted_run(cfg.name):
                    st.toast(f"Deleted '{cfg.name}'")
                st.rerun()

        saved = list_scripted_runs()
        if saved:
            c_pick, c_load = st.columns([3, 1])
            with c_pick:
                pick = st.selectbox(
                    "Load existing preset", saved, key="day_sim_scripted_pick",
                )
            with c_load:
                st.write("")
                if st.button("📂 Load", key="day_sim_scripted_load", width="stretch"):
                    loaded = load_scripted_run(pick)
                    if loaded is not None:
                        st.session_state[_SCRIPTED_KEY] = loaded
                        st.rerun()

    with st.container(border=True):
        st.markdown("**Run-wide options**")
        c1, c2, c3 = st.columns(3)
        with c1:
            cfg.paid_season_pass = st.toggle(
                "💎 Paid season pass", value=cfg.paid_season_pass,
                key="day_sim_scripted_paid",
            )
        with c2:
            cfg.auto_open_daily_packs = st.toggle(
                "🎁 Auto-open daily packs", value=cfg.auto_open_daily_packs,
                key="day_sim_scripted_autopacks",
            )
        with c3:
            cfg.token_spend_policy = st.selectbox(
                "Token spend policy",
                options=["cheapest_first", "focus_hero", "round_robin"],
                index=["cheapest_first", "focus_hero", "round_robin"].index(cfg.token_spend_policy),
                key="day_sim_scripted_policy",
            )
        if cfg.token_spend_policy == "focus_hero":
            hero_ids = [h.hero_id for h in config.heroes]
            if hero_ids:
                if cfg.focus_hero_id not in hero_ids:
                    cfg.focus_hero_id = hero_ids[0]
                cfg.focus_hero_id = st.selectbox(
                    "Focus hero", hero_ids,
                    index=hero_ids.index(cfg.focus_hero_id),
                    format_func=lambda hid: next((h.name for h in config.heroes if h.hero_id == hid), hid),
                    key="day_sim_scripted_focus_hero",
                )

    with st.container(border=True):
        st.markdown("**Daily schedule**")
        st.caption(
            "One row per day. Days not listed run baseline (auto-pack only). "
            "Day 0 is the FTUE day (FTUE auto-runs on Start/Reset)."
        )
        rows = []
        for d in sorted(cfg.schedule, key=lambda d: d.day):
            rows.append({
                "Day": d.day,
                "Chapters beaten": d.chapters_beaten,
                "Season pass target step": d.season_pass_target_step or 0,
            })
        if not rows:
            rows = [{"Day": 0, "Chapters beaten": 0, "Season pass target step": 0}]
        sched_df = pd.DataFrame(rows)
        edited = st.data_editor(
            sched_df,
            column_config={
                "Day": st.column_config.NumberColumn("Day", min_value=0, max_value=2000, step=1),
                "Chapters beaten": st.column_config.NumberColumn("Chapters beaten", min_value=0, max_value=50, step=1),
                "Season pass target step": st.column_config.NumberColumn(
                    "SP target step (0 = skip)", min_value=0, max_value=200, step=1,
                ),
            },
            width="stretch", hide_index=True, num_rows="dynamic",
            key="day_sim_scripted_schedule",
        )
        new_sched: List[ScriptedRunDay] = []
        seen_days: set[int] = set()
        for _, row in edited.iterrows():
            try:
                day = int(row["Day"])
            except (ValueError, TypeError):
                continue
            if day in seen_days:
                continue
            seen_days.add(day)
            target = int(row["Season pass target step"] or 0)
            new_sched.append(ScriptedRunDay(
                day=day,
                chapters_beaten=int(row["Chapters beaten"] or 0),
                season_pass_target_step=target if target > 0 else None,
            ))
        cfg.schedule = sorted(new_sched, key=lambda d: d.day)

    with st.container(border=True):
        st.markdown("**Run**")
        c_n, c_btn = st.columns([1, 1])
        with c_n:
            num_days = st.number_input(
                "Days to advance", min_value=1, max_value=730, value=7, step=1,
                key="day_sim_scripted_num_days",
            )
        with c_btn:
            st.write("")
            if st.button("▶ Run scripted days", type="primary",
                         key="day_sim_scripted_run", width="stretch"):
                state = st.session_state[_STATE_KEY]
                rng = _rng()
                schedule_by_day = {d.day: d for d in cfg.schedule}
                opened_all: List[Dict[str, Any]] = []
                for _ in range(int(num_days)):
                    current_day = state["day"]
                    day_entry = schedule_by_day.get(current_day)
                    summary = scripted_run_one_day(state, config, cfg, day_entry, rng)
                    _log(summary["log_lines"])
                    opened_all.extend(summary["opened_packs"])
                    # Advance day counter (mirrors the manual top-bar Next Day flow).
                    _snapshot_history(state)
                    state["day"] += 1
                    unlocks = ds.advance_day(state["game_state"], state["day"], config)
                    state["daily_used"] = set()
                    _log([f"── Advanced to day {state['day']} (scripted) ──"] + unlocks)
                    # Auto-beat the cohort's chapters on the new day — same
                    # rule as the manual "Next day" flow, so scripted runs
                    # don't silently skip the chapter rhythm.
                    chapters_today = _chapters_for_sim_day(
                        state.get("chapters_per_day", []), state["day"]
                    )
                    if chapters_today > 0:
                        _auto_beat_chapters(state, config, chapters_today)
                        opened_all.extend(state.get("last_pack_results") or [])
                    _snapshot_history(state)
                if opened_all:
                    state["last_pack_results"] = opened_all[-10:]
                st.rerun()


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


# ─── Charts ──────────────────────────────────────────────────────────────────

def _render_charts(config: HeroCardConfig, game_state: HeroCardGameState) -> None:
    history = st.session_state[_STATE_KEY].get("history") or []
    if len(history) < 2:
        st.info(
            "Charts populate once you have at least two day-snapshots. "
            "Click **Next day →** to advance time, then return here."
        )
        return

    # --- Bluestars over time ---
    with st.container(border=True):
        st.markdown("**Bluestars over time**")
        bs_df = pd.DataFrame(
            [{"Day": s["day"], "Bluestars": s["bluestars"]} for s in history]
        ).set_index("Day")
        st.line_chart(bs_df, height=260)
        c1, c2, c3 = st.columns(3)
        c1.metric("Current", f"{history[-1]['bluestars']:,}")
        c2.metric("Δ since day 0", f"{history[-1]['bluestars'] - history[0]['bluestars']:,}")
        days_span = max(1, history[-1]["day"] - history[0]["day"])
        c3.metric("Avg / day", f"{(history[-1]['bluestars'] - history[0]['bluestars']) / days_span:,.1f}")

    # --- Hero XP / level ---
    with st.container(border=True):
        st.markdown("**Hero progression (fractional level over time)**")
        st.caption(
            "Plotted value = `hero_level + xp / xp_to_next_level`, so a smooth line "
            "across level-ups. Pick heroes to compare."
        )
        all_heroes = sorted({hero_id for s in history for hero_id in s["heroes"]})
        if not all_heroes:
            st.caption("No heroes unlocked yet.")
            return
        default = all_heroes[: min(4, len(all_heroes))]
        picked = st.multiselect(
            "Heroes",
            options=all_heroes,
            default=default,
            key="day_sim_chart_hero_pick",
            format_func=lambda hid: (_hero_def(config, hid).name if _hero_def(config, hid) else hid),
        )
        if picked:
            level_rows = []
            xp_rows = []
            avg_rows = []
            for s in history:
                level_entry = {"Day": s["day"]}
                xp_entry = {"Day": s["day"]}
                avg_entry = {"Day": s["day"]}
                for hid in picked:
                    h = s["heroes"].get(hid)
                    if h is None:
                        continue
                    hd = _hero_def(config, hid)
                    needed = _xp_to_next_level(hd, h["level"])
                    frac = (h["xp"] / needed) if needed > 0 else 0.0
                    label = hd.name if hd else hid
                    level_entry[label] = h["level"] + frac
                    xp_entry[label] = h["xp"]
                    avg_entry[label] = h["avg_card_level"]
                level_rows.append(level_entry)
                xp_rows.append(xp_entry)
                avg_rows.append(avg_entry)

            st.line_chart(pd.DataFrame(level_rows).set_index("Day"), height=280)

            with st.expander("Raw XP (resets on level-up)", expanded=False):
                st.line_chart(pd.DataFrame(xp_rows).set_index("Day"), height=240)
            with st.expander("Average card level per hero", expanded=False):
                st.line_chart(pd.DataFrame(avg_rows).set_index("Day"), height=240)

            # Snapshot table for the latest day
            st.caption(f"Latest snapshot (day {history[-1]['day']}):")
            snap_rows = []
            for hid in picked:
                h = history[-1]["heroes"].get(hid)
                if h is None:
                    continue
                hd = _hero_def(config, hid)
                needed = _xp_to_next_level(hd, h["level"])
                snap_rows.append({
                    "Hero": hd.name if hd else hid,
                    "Level": h["level"],
                    "XP toward next": f"{h['xp']:,} / {needed:,}" if needed else "MAX",
                    "Jokers": h["jokers"],
                    "Unlocked cards": h["unlocked_cards"],
                    "Avg card lvl": round(h["avg_card_level"], 2),
                })
            if snap_rows:
                st.dataframe(pd.DataFrame(snap_rows), hide_index=True, width="stretch")


# ─── Activity log ────────────────────────────────────────────────────────────

def _render_activity_log() -> None:
    log: List[str] = st.session_state[_STATE_KEY]["event_log"]
    if not log:
        st.caption("No activity yet.")
        return
    shown = log[-_MAX_LOG:][::-1]
    st.text("\n".join(shown))
