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
from simulation.variants.variant_b.scripted_runner import (
    run_one_day as scripted_run_one_day,
    beat_chapters_by_bluestars as _beat_chapters_by_bluestars,
)
from simulation.variants.variant_b.chapter_schedule import (
    chapters_for_sim_day as _chapters_for_sim_day,
    chapters_for_bluestars as _chapters_for_bluestars,
    load_cohort_chapters as _load_cohort_chapters,
    load_default_bluestar_thresholds as _load_bluestar_thresholds,
)


_STATE_KEY = "day_sim"
_MAX_LOG = 120

# Type+color buckets for upgrade / bluestar-source breakdowns. Mirrors the
# Monte Carlo dashboard: HERO buckets use strong hues, SHARED buckets lighter
# tints, premium-pack bluestars get their own violet bucket.
_BREAKDOWN_BUCKETS = ["HERO_GOLD", "HERO_BLUE", "HERO_GRAY",
                      "SHARED_GOLD", "SHARED_BLUE", "SHARED_GRAY"]
_BLUESTAR_SOURCE_BUCKETS = _BREAKDOWN_BUCKETS + ["PREMIUM_PACK"]
_BUCKET_LABELS = {
    "HERO_GOLD": "Hero · Gold", "HERO_BLUE": "Hero · Blue", "HERO_GRAY": "Hero · Gray",
    "SHARED_GOLD": "Shared · Gold", "SHARED_BLUE": "Shared · Blue",
    "SHARED_GRAY": "Shared · Gray", "PREMIUM_PACK": "Premium pack",
}
_BUCKET_COLORS = {
    "HERO_GOLD": "#CA8A04", "HERO_BLUE": "#2563EB", "HERO_GRAY": "#6B7280",
    "SHARED_GOLD": "#FCD34D", "SHARED_BLUE": "#93C5FD", "SHARED_GRAY": "#D1D5DB",
    "PREMIUM_PACK": "#7C3AED",
}


def _hero_event_bucket(evt: Dict[str, Any]) -> str:
    return f"HERO_{evt.get('rarity', '')}"


def _shared_event_bucket(evt: Dict[str, Any]) -> str:
    color = str(evt.get("category", "")).replace("_SHARED", "")
    return f"SHARED_{color}"


def _accumulate_upgrade_breakdown(
    state: Dict[str, Any],
    hero_events: List[Dict[str, Any]],
    shared_events: List[Dict[str, Any]],
) -> None:
    """Fold raw upgrade events into the cumulative per-bucket upgrade-count and
    bluestar-source counters (type × color). Premium-pack bluestars are tracked
    separately via `_accumulate_premium_bluestars`."""
    upg = state.setdefault("upg_by_bucket", {})
    bs = state.setdefault("bs_by_source", {})
    for evt in hero_events:
        key = _hero_event_bucket(evt)
        upg[key] = upg.get(key, 0) + 1
        bs[key] = bs.get(key, 0) + int(evt.get("bluestars_earned", 0))
    for evt in shared_events:
        key = _shared_event_bucket(evt)
        upg[key] = upg.get(key, 0) + 1
        bs[key] = bs.get(key, 0) + int(evt.get("bluestars_earned", 0))


def _accumulate_premium_bluestars(state: Dict[str, Any], amount: int) -> None:
    if amount <= 0:
        return
    bs = state.setdefault("bs_by_source", {})
    bs["PREMIUM_PACK"] = bs.get("PREMIUM_PACK", 0) + int(amount)


def _snapshot_history(state: Dict[str, Any]) -> None:
    """Capture a per-day snapshot for the history charts."""
    game_state: HeroCardGameState = state["game_state"]
    snap = {
        "day": state["day"],
        "bluestars": game_state.total_bluestars,
        "coins": game_state.coins,
        "upgrades_hero": state.get("upgrades_hero", 0),
        "upgrades_shared": state.get("upgrades_shared", 0),
        "upg_by_bucket": dict(state.get("upg_by_bucket", {})),
        "bs_by_source": dict(state.get("bs_by_source", {})),
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


def _record_bluestars(state: Dict[str, Any]) -> None:
    """Append a bluestar sample to the continuous trace whenever it changes.

    Called on every rerun (i.e. after every action — pack open, upgrade,
    chapter beat, day advance), so the trace captures the full bluestar curve
    rather than only day-boundary snapshots.
    """
    trace: List[Dict[str, Any]] = state.setdefault("bs_trace", [])
    bs = state["game_state"].total_bluestars
    if trace and trace[-1]["bluestars"] == bs:
        return  # no change since last sample — don't pad the chart
    trace.append({"step": len(trace), "day": state["day"], "bluestars": bs})


def _per_card_upgrade_lines(
    hero_events: List[Dict[str, Any]],
    shared_events: List[Dict[str, Any]],
) -> List[str]:
    """Collapse raw upgrade events into one human-readable line per card so the
    user can see exactly which cards leveled, how far, and at what cost."""
    agg: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for e in hero_events:
        key = f"{e['hero_id']}/{e['card_id']}"
        a = agg.get(key)
        if a is None:
            a = {"lo": e["old_level"], "hi": e["new_level"], "n": 0,
                 "dupes": 0, "jokers": 0, "bs": 0}
            agg[key] = a
            order.append(key)
        a["lo"] = min(a["lo"], e["old_level"])
        a["hi"] = max(a["hi"], e["new_level"])
        a["n"] += 1
        a["dupes"] += e["dupes_spent"]
        a["jokers"] += e.get("jokers_spent", 0)
        a["bs"] += e["bluestars_earned"]
    for e in shared_events:
        key = f"shared/{e['card_id']}"
        a = agg.get(key)
        if a is None:
            a = {"lo": e["old_level"], "hi": e["new_level"], "n": 0,
                 "dupes": 0, "jokers": 0, "bs": 0}
            agg[key] = a
            order.append(key)
        a["lo"] = min(a["lo"], e["old_level"])
        a["hi"] = max(a["hi"], e["new_level"])
        a["n"] += 1
        a["dupes"] += e["dupes_spent"]
        a["bs"] += e["bluestars_earned"]

    lines: List[str] = []
    for key in order:
        a = agg[key]
        joker = f", {a['jokers']} jokers" if a["jokers"] else ""
        lines.append(
            f"    ↑ {key}: L{a['lo']}→L{a['hi']} (×{a['n']}, "
            f"{a['dupes']} dupes{joker}, +{a['bs']} ⭐)"
        )
    return lines


def _run_auto_upgrade(state: Dict[str, Any], config: HeroCardConfig) -> int:
    """Greedily upgrade every eligible card (hero + shared), mirroring the
    manual "Greedy auto-upgrade" button. Updates the cumulative counters and
    logs only when something actually upgraded. Returns the number of upgrades.
    """
    game_state: HeroCardGameState = state["game_state"]
    hero_events, total_xp, total_bs, tree_acts = attempt_hero_upgrades(game_state, config)
    shared_events, shared_bs = attempt_shared_upgrades(game_state, config)
    n = len(hero_events) + len(shared_events)
    if n:
        state["upgrades_hero"] += len(hero_events)
        state["upgrades_shared"] += len(shared_events)
        _accumulate_upgrade_breakdown(state, hero_events, shared_events)
        tree_count = sum(len(v) for v in tree_acts.values())
        _log([
            f"Auto-upgrade: {len(hero_events)} hero (+{total_xp} XP, "
            f"+{total_bs} bluestars), {len(shared_events)} shared "
            f"(+{shared_bs} bluestars), {tree_count} skill-tree activations"
        ] + _per_card_upgrade_lines(hero_events, shared_events))
    return n


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

# Chapter-beating cohorts whose bluestar thresholds gate progression. These
# come from data/defaults/chapter_bluestar_thresholds.json. "Calendar" falls
# back to the legacy fixed chapters-per-day cadence (Average/P75/P90).
_BS_GATING_OPTIONS = ["Non-Payer", "Mid-Payer", "Payer", "All", "Calendar"]
_DEFAULT_BS_GATING = "Non-Payer"


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
    state["game_state"].chapters_beaten += n
    state["last_pack_results"] = last_results
    _log([f"Auto-beat {n} chapter(s) on day {state['day']} → {n} EndOfChapter pack(s) opened"])
    _log_pack_results(last_results)


def _reset(config: HeroCardConfig, seed: Optional[int]) -> None:
    rng = Random(seed if seed and seed > 0 else None)
    prev = st.session_state.get(_STATE_KEY, {})
    paid_pass = prev.get("paid_pass", False)
    auto_upgrade = prev.get("auto_upgrade", False)
    cohort = prev.get("cohort") or _DEFAULT_COHORT
    chapters_per_day = _load_cohort_chapters(cohort)
    bs_gating = prev.get("bs_gating") or _DEFAULT_BS_GATING
    bs_thresholds = [] if bs_gating == "Calendar" else _load_bluestar_thresholds(bs_gating)
    st.session_state[_STATE_KEY] = {
        "game_state": ds.init_state(config),
        "day": 0,
        "season_pass_step": 1,
        "paid_pass": paid_pass,
        "auto_upgrade": auto_upgrade,
        "bs_trace": [],
        "extras": ds.init_extras(),
        "event_log": [],
        "rng": rng,
        "rng_seed": seed,
        "last_pack_results": [],
        "last_premium_result": None,
        "daily_used": set(),
        "cohort": cohort,
        "chapters_per_day": chapters_per_day,
        "bs_gating": bs_gating,
        "bs_thresholds": bs_thresholds,
        "upgrades_hero": 0,
        "upgrades_shared": 0,
        "upg_by_bucket": {},
        "bs_by_source": {},
    }
    _log([f"Day 0 (install day) — fresh simulation (seed={seed or 'random'})"])
    state = st.session_state[_STATE_KEY]
    state["history"] = []
    ftue_lines = ftue.run_ftue(state["game_state"], config, state["extras"])
    _log(ftue_lines)

    # FTUE bluestars may already cross several hero unlock thresholds; bring the
    # roster up to date so day-0 reflects progression (heroes unlock by
    # bluestars, not by calendar day).
    from simulation.variants.variant_b.hero_deck import unlock_heroes_by_day
    unlocked_names = unlock_heroes_by_day(state["game_state"], config)
    if unlocked_names:
        _log(["Heroes unlocked (post-FTUE): " + ", ".join(unlocked_names)])

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

    if auto_upgrade:
        _run_auto_upgrade(state, config)
    _snapshot_history(state)
    _record_bluestars(state)


# ─── Top-level render ────────────────────────────────────────────────────────

def render_variant_b_day_simulator() -> None:
    st.title("Day-by-day simulator")
    st.caption(
        "Manual, step-by-step Variant B simulator. Open daily packs (with "
        "evolution rerolls), claim season-pass steps (packs auto-open), open "
        "Hero Unique Packs, and upgrade cards one at a time."
    )

    variant_id = st.session_state.get("active_variant", "variant_b")
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

    # Every action (pack open, season-pass claim, chapter beat, day advance)
    # ends in st.rerun(), so this block runs once per action. When auto-upgrade
    # is on, greedily upgrade everything affordable; then record the resulting
    # bluestar balance into the continuous trace for the chart.
    if state.get("auto_upgrade"):
        _run_auto_upgrade(state, config)
    _record_bluestars(state)

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
        c_seed, c_reset, c_cohort, c_gate, c_paid, c_auto, c_day, c_chap, c_up, c_next = st.columns(
            [1.0, 1.0, 1.1, 1.2, 1.1, 1.1, 0.7, 0.9, 0.9, 1.2]
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
        with c_gate:
            current_gate = (
                st.session_state.get(_STATE_KEY, {}).get("bs_gating")
                or _DEFAULT_BS_GATING
            )
            picked_gate = st.selectbox(
                "Chapter gating",
                options=_BS_GATING_OPTIONS,
                index=_BS_GATING_OPTIONS.index(current_gate)
                    if current_gate in _BS_GATING_OPTIONS else 0,
                key="day_sim_bs_gating",
                help="Bluestar cohorts beat chapters when total bluestars cross "
                     "that cohort's thresholds (matches the in-game methodology). "
                     "'Calendar' uses the legacy fixed chapters-per-day cadence.",
            )
            if _STATE_KEY in st.session_state and picked_gate != current_gate:
                st.session_state[_STATE_KEY]["bs_gating"] = picked_gate
                st.session_state[_STATE_KEY]["bs_thresholds"] = (
                    [] if picked_gate == "Calendar" else _load_bluestar_thresholds(picked_gate)
                )
                _log([f"Chapter gating switched to **{picked_gate}**."])
        with c_paid:
            st.write("")
            if _STATE_KEY in st.session_state:
                st.session_state[_STATE_KEY]["paid_pass"] = st.toggle(
                    "💎 Paid season pass",
                    value=st.session_state[_STATE_KEY].get("paid_pass", False),
                    key="day_sim_paid_toggle",
                )
        with c_auto:
            st.write("")
            if _STATE_KEY in st.session_state:
                st.session_state[_STATE_KEY]["auto_upgrade"] = st.toggle(
                    "⚡ Auto-upgrade",
                    value=st.session_state[_STATE_KEY].get("auto_upgrade", False),
                    key="day_sim_auto_upgrade_toggle",
                    help="When on, greedily upgrade every card you can afford "
                         "(dupes + coins, lowest-level first) after each action "
                         "— pack open, season-pass claim, chapter beat, day advance.",
                )
        with c_day:
            if _STATE_KEY in st.session_state:
                st.metric("Day", st.session_state[_STATE_KEY]["day"])
        with c_chap:
            if _STATE_KEY in st.session_state:
                st.metric(
                    "Chapters",
                    st.session_state[_STATE_KEY]["game_state"].chapters_beaten,
                )
        with c_up:
            if _STATE_KEY in st.session_state:
                s = st.session_state[_STATE_KEY]
                st.metric(
                    "Upgrades",
                    s.get("upgrades_hero", 0) + s.get("upgrades_shared", 0),
                    help="Cumulative card upgrades (hero + shared) across the run.",
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
                    # Beat chapters. Bluestar gating beats every chapter the
                    # player's current bluestars can afford (matches the in-game
                    # methodology); the legacy "Calendar" mode beats a fixed
                    # per-day count from the chosen cohort profile.
                    bs_thresholds = state.get("bs_thresholds") or []
                    if bs_thresholds:
                        ch_res = _beat_chapters_by_bluestars(
                            state["game_state"], config, bs_thresholds, _rng(),
                            auto_upgrade=False,
                        )
                        if ch_res["chapters"]:
                            state["last_pack_results"] = ch_res["opened"]
                            _log(ch_res["log_lines"])
                            _log_pack_results(ch_res["opened"])
                    else:
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
            game_state.chapters_beaten += 1
            _log([f"Beat chapter #{game_state.chapters_beaten} → EndOfChapter pack opened"])
            _log_pack_results([r])
            st.rerun()
        with b_beat_n:
            st.caption(f"Total chapters beaten: **{game_state.chapters_beaten}**")

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
        distinct_types = {
            (c["kind"], c.get("hero_id") or c.get("category"), c.get("card_name"))
            for r in results for c in r["cards"]
        }
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Cards pulled", total_cards)
        s2.metric("Card types", len(distinct_types))
        s3.metric("Coins gained", f"{total_coins:,}")
        s4.metric("Jokers gained", total_jokers)

        # Flat, always-visible pull-by-pull list across every pack opened in
        # this action (one row per card pulled).
        flat_rows = []
        for idx, r in enumerate(results):
            for c in r["cards"]:
                base = c.get("dupe_base_cost", 0) or 0
                eff = c.get("dupe_effective_pct", 0.0) or 0.0
                flat_rows.append({
                    "Pack #": idx + 1,
                    "Kind": "Hero" if c["kind"] == "hero" else "Shared",
                    "Owner": c.get("hero_id") if c["kind"] == "hero" else c.get("category"),
                    "Card": c["card_name"],
                    "Rarity": c["rarity"] if c["kind"] == "hero" else "—",
                    "Lvl before": c["level_before"],
                    "Dupes/Need": f"{c['duplicates_received']} / {base}" if base else f"{c['duplicates_received']}",
                    "% of next lvl": f"{eff * 100:.1f}%" if base else "—",
                    "Coins": c["coins_earned"],
                })
        if flat_rows:
            st.markdown("**Every pull**")
            st.dataframe(pd.DataFrame(flat_rows), hide_index=True, width="stretch")

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
            amt = pull.get("reward_amount", 0)
            game_state.total_bluestars += amt
            _accumulate_premium_bluestars(state, amt)
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
                st.session_state[_STATE_KEY]["upgrades_hero"] += len(hero_events)
                st.session_state[_STATE_KEY]["upgrades_shared"] += len(shared_events)
                _accumulate_upgrade_breakdown(
                    st.session_state[_STATE_KEY], hero_events, shared_events
                )
                _log([
                    f"Auto-upgrade: {len(hero_events)} hero upgrades (+{total_xp} XP, +{total_bs} bluestars), "
                    f"{len(shared_events)} shared upgrades (+{shared_bs} bluestars), "
                    f"{tree_count} skill tree activations"
                ] + _per_card_upgrade_lines(hero_events, shared_events))
                st.rerun()
        with bc2:
            st.caption("Auto-upgrade spends duplicates greedily (lowest-level first), mirroring the daily orchestrator. Each card that levels is listed in the activity log.")

    if game_state.heroes:
        _render_skill_tree_panel(config, game_state)

    if not game_state.heroes and not game_state.shared_cards:
        st.caption("Nothing to upgrade yet.")
        return

    st.caption(
        "A card is upgradeable once you hold enough **duplicates (+ jokers)**. "
        "**Coins need** is the coin cost that gets spent — it does NOT block the "
        "upgrade (coins can go negative), so ⬆ enables on duplicates alone."
    )

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


_DEFAULT_SCRIPTED_PRESET = "AvgPaid-Balanced-14d"


def _ensure_scripted_cfg() -> ScriptedRunConfig:
    """Return the in-memory scripted-run config.

    On first session entry, falls back to the canonical "average paid
    player" demo preset so the Scenario Play tab opens populated. If that
    file is missing (e.g. fresh clone before profiles ship), creates a
    blank config.
    """
    cfg = st.session_state.get(_SCRIPTED_KEY)
    if cfg is None or not isinstance(cfg, ScriptedRunConfig):
        cfg = load_scripted_run(_DEFAULT_SCRIPTED_PRESET) or ScriptedRunConfig(name="untitled", schedule=[])
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

        g1, g2 = st.columns(2)
        with g1:
            _gate_opts = ["calendar", "bluestar"]
            cfg.chapter_gating = st.selectbox(
                "Chapter gating",
                options=_gate_opts,
                index=_gate_opts.index(cfg.chapter_gating) if cfg.chapter_gating in _gate_opts else 0,
                key="day_sim_scripted_gating",
                help="'bluestar' beats chapters by bluestar thresholds at end of day "
                     "(matches the in-game methodology); 'calendar' uses the per-day "
                     "schedule's 'Chapters beaten' column.",
            )
            if cfg.chapter_gating == "bluestar":
                _bs_cohorts = ["Non-Payer", "Mid-Payer", "Payer", "All"]
                current = cfg.bluestar_cohort if cfg.bluestar_cohort in _bs_cohorts else "Non-Payer"
                cfg.bluestar_cohort = st.selectbox(
                    "Bluestar cohort", options=_bs_cohorts,
                    index=_bs_cohorts.index(current),
                    key="day_sim_scripted_bs_cohort",
                )
        with g2:
            sp_per_day = st.number_input(
                "Season-pass steps / day (0 = use schedule)",
                min_value=0, max_value=90,
                value=int(cfg.season_pass_steps_per_day or 0),
                step=1, key="day_sim_scripted_sp_per_day",
                help="Methodology = 9 steps/day. Overrides the per-day schedule "
                     "target when > 0.",
            )
            cfg.season_pass_steps_per_day = int(sp_per_day) if sp_per_day > 0 else None

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
                # When the preset uses bluestar gating, the scenario cohort is
                # authoritative for this run — sync thresholds into state so
                # run_one_day beats chapters against the right curve.
                if cfg.chapter_gating == "bluestar":
                    state["bs_thresholds"] = _load_bluestar_thresholds(cfg.bluestar_cohort)
                for _ in range(int(num_days)):
                    current_day = state["day"]
                    day_entry = schedule_by_day.get(current_day)
                    summary = scripted_run_one_day(state, config, cfg, day_entry, rng)
                    _log(summary["log_lines"])
                    opened_all.extend(summary["opened_packs"])
                    state["upgrades_hero"] += summary.get("hero_upgrades", 0)
                    state["upgrades_shared"] += summary.get("shared_upgrades", 0)
                    _accumulate_upgrade_breakdown(
                        state,
                        summary.get("hero_events", []),
                        summary.get("shared_events", []),
                    )
                    # Advance day counter (mirrors the manual top-bar Next Day flow).
                    _snapshot_history(state)
                    state["day"] += 1
                    unlocks = ds.advance_day(state["game_state"], state["day"], config)
                    state["daily_used"] = set()
                    _log([f"── Advanced to day {state['day']} (scripted) ──"] + unlocks)
                    # Calendar gating beats the cohort's chapters on the new
                    # day. Under bluestar gating, run_one_day already beat the
                    # affordable chapters at end of day — don't double-beat.
                    if cfg.chapter_gating != "bluestar":
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
        # Coins are spent but do NOT gate upgrades (same rule as the greedy
        # engine), so availability depends on duplicates + jokers only.
        enabled = card.duplicates + hs.joker_count >= dupe_cost

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
                    st.session_state[_STATE_KEY]["upgrades_hero"] += 1
                    _accumulate_upgrade_breakdown(st.session_state[_STATE_KEY], [evt], [])
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
        # Coins are spent but do NOT gate upgrades (same rule as the engine).
        enabled = card.duplicates >= dupe_cost

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
                    st.session_state[_STATE_KEY]["upgrades_shared"] += 1
                    _accumulate_upgrade_breakdown(st.session_state[_STATE_KEY], [], [evt])
                    _log(
                        f"Upgrade {card.id} ({cat}): L{evt['old_level']}→L{evt['new_level']} "
                        f"(-{evt['dupes_spent']} dupes, -{evt['coins_spent']} coins, +{evt['bluestars_earned']} bluestars)"
                    )
                st.rerun()


# ─── Charts ──────────────────────────────────────────────────────────────────

def _render_breakdown_chart(
    history: List[Dict[str, Any]],
    state_key: str,
    buckets: List[str],
    value_name: str,
) -> None:
    """Stacked per-day bar chart of cumulative-dict deltas, plus lifetime totals.

    `state_key` selects the per-snapshot cumulative dict (`upg_by_bucket` or
    `bs_by_source`); `buckets` fixes column order. Only buckets with a nonzero
    lifetime total are shown.
    """
    totals = history[-1].get(state_key, {}) or {}
    active = [b for b in buckets if totals.get(b, 0)]
    if not active:
        st.caption("No data yet.")
        return

    rows = []
    prev = history[0].get(state_key, {}) or {}
    for s in history[1:]:
        cur = s.get(state_key, {}) or {}
        row = {"Day": s["day"]}
        for b in active:
            row[_BUCKET_LABELS[b]] = cur.get(b, 0) - prev.get(b, 0)
        rows.append(row)
        prev = cur
    if not rows:
        st.caption("No day-to-day deltas yet.")
        return

    df = pd.DataFrame(rows).set_index("Day")
    st.bar_chart(df, height=260, color=[_BUCKET_COLORS[b] for b in active])

    cols = st.columns(len(active))
    grand = sum(totals.get(b, 0) for b in active) or 1
    for col, b in zip(cols, active):
        col.metric(
            _BUCKET_LABELS[b],
            f"{totals.get(b, 0):,}",
            delta=f"{100 * totals.get(b, 0) / grand:.0f}%",
            delta_color="off",
        )
    st.caption(f"Totals are lifetime {value_name} per bucket.")


def _render_charts(config: HeroCardConfig, game_state: HeroCardGameState) -> None:
    # --- Continuous bluestar trace (sampled on every action) ---
    bs_trace = st.session_state[_STATE_KEY].get("bs_trace") or []
    if len(bs_trace) >= 2:
        with st.container(border=True):
            st.markdown("**Bluestars (every change)**")
            st.caption(
                "Sampled on every action — pack opens, upgrades, chapter beats, "
                "day advances — so you see the full bluestar curve, not just "
                "day boundaries. X-axis is the action number."
            )
            trace_df = pd.DataFrame(
                [{"Event #": s["step"], "Bluestars": s["bluestars"]} for s in bs_trace]
            ).set_index("Event #")
            st.line_chart(trace_df, height=260)
            t1, t2, t3 = st.columns(3)
            t1.metric("Current", f"{bs_trace[-1]['bluestars']:,}")
            t2.metric("Samples", f"{len(bs_trace):,}")
            t3.metric("Latest day", bs_trace[-1]["day"])

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

    # --- Upgrades by type & color ---
    with st.container(border=True):
        st.markdown("**Upgrades per day — by type & color**")
        st.caption(
            "Per-day delta in cumulative upgrade count, split by card type "
            "(Hero vs Shared) and color. Counts upgrades from the auto-upgrade "
            "button, single-card buttons, and scripted runs."
        )
        _render_breakdown_chart(
            history, "upg_by_bucket", _BREAKDOWN_BUCKETS, "upgrades"
        )

    # --- Bluestar sources by type & color ---
    with st.container(border=True):
        st.markdown("**Bluestar sources per day — by type & color**")
        st.caption(
            "Per-day delta in bluestars earned, split by source — card upgrades "
            "(by type & color) and direct premium-pack grants."
        )
        _render_breakdown_chart(
            history, "bs_by_source", _BLUESTAR_SOURCE_BUCKETS, "bluestars"
        )

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
