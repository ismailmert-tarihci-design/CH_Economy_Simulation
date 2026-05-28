"""Variant B dashboard — Hero Card System.

Displays hero progression, card levels, skill tree progress,
premium economics, and standard bluestar/coin charts.
"""

from typing import Any, Dict

import plotly.graph_objects as go
import streamlit as st

# Palette — strong contrast on white
_BLUE = "#2563EB"
_GREEN = "#16A34A"
_AMBER = "#CA8A04"
_RED = "#DC2626"
_VIOLET = "#7C3AED"
_ORANGE = "#EA580C"
_TEAL = "#0891B2"
_PINK = "#DB2777"
_HERO_COLORS = [_BLUE, _GREEN, _ORANGE, _RED, _VIOLET, _AMBER, _TEAL, _PINK,
                "#0284C7", "#059669", "#D97706", "#E11D48", "#6D28D9", "#C2410C", "#0E7490", "#BE185D"]


def _styled_fig(title: str = "") -> go.Figure:
    """Create a pre-styled Plotly figure for the light theme."""
    fig = go.Figure()
    fig.update_layout(
        title=dict(text=title, font=dict(size=16)),
        template="plotly_white",
        hovermode="x unified",
        margin=dict(l=40, r=20, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def render_variant_b_dashboard() -> None:
    if "sim_result" not in st.session_state:
        st.info("No simulation results yet. Run a simulation first.", icon=":material/info:")
        return

    result = st.session_state.sim_result
    mode = st.session_state.get("sim_mode", "deterministic")

    st.title("Hero card system dashboard")

    _render_save_popover(result, mode)

    if mode != "deterministic":
        _render_mc_summary(result)
        _render_mc_bluestar_chart(result)
        _render_mc_chapter_chart(result)
        with st.container(border=True):
            _render_mc_per_hero_breakdown(result)
        return

    snapshots = result.daily_snapshots
    if not snapshots:
        st.info("No data in simulation results.", icon=":material/info:")
        return

    config = st.session_state.get("config")
    hero_name_map = {}
    if config and hasattr(config, "heroes"):
        hero_name_map = {h.hero_id: h.name for h in config.heroes}

    # KPI row
    _render_kpis(result, snapshots)

    # Charts in a 2-column grid
    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            _render_bluestar_chart(snapshots)
    with col2:
        with st.container(border=True):
            _render_coin_chart(snapshots)

    col3, col4 = st.columns(2)
    with col3:
        with st.container(border=True):
            _render_shared_level_chart(snapshots, hero_name_map)
    with col4:
        with st.container(border=True):
            _render_hero_card_level_chart(snapshots, hero_name_map)

    with st.container(border=True):
        _render_xp_chart(snapshots, hero_name_map)

    # Chapter cadence + EndOfChapterPack rewards
    with st.container(border=True):
        _render_chapter_chart(snapshots)
        _render_pack_counts_breakdown(snapshots)

    # Per-hero breakdown
    with st.container(border=True):
        _render_per_hero_breakdown(snapshots, hero_name_map)

    # Hero Token hunger — surfaces how token income is keeping up with the
    # skill-tree token cost for each hero (per-hero "needs N more tokens").
    with st.container(border=True):
        _render_hero_token_hunger(result, snapshots, config, hero_name_map)

    # Summary sections
    col5, col6, col7 = st.columns(3)
    with col5:
        _render_premium_pack_summary(result, snapshots)
    with col6:
        _render_joker_summary(snapshots)
    with col7:
        _render_skill_tree_summary(snapshots)


def _render_kpis(result: Any, snapshots: list) -> None:
    chapters_total = (
        int(getattr(snapshots[-1], "chapters_beaten_total", 0)) if snapshots else 0
    )
    eoc_packs_total = sum(
        int(s.pack_counts_by_type.get("EndOfChapterPack", 0)) for s in snapshots
    )
    with st.container(horizontal=True):
        st.metric("Total bluestars", f"{result.total_bluestars:,}", border=True)
        st.metric("Coins earned", f"{result.total_coins_earned:,}", border=True)
        st.metric("Total upgrades", f"{sum(result.total_upgrades.values()):,}", border=True)
        if result.final_hero_levels:
            max_lvl = max(result.final_hero_levels.values())
            avg_lvl = sum(result.final_hero_levels.values()) / len(result.final_hero_levels)
            st.metric("Max hero level", f"Lv {max_lvl} (avg {avg_lvl:.1f})", border=True)
        else:
            st.metric("Max hero level", "—", border=True)
        st.metric("Jokers received", f"{result.total_jokers_received:,}", border=True)
        st.metric("Diamonds spent", f"{result.total_premium_diamonds_spent:,}", border=True)
        st.metric(
            "Chapters beaten",
            f"{chapters_total:,}",
            delta=f"{eoc_packs_total:,} EoC packs",
            delta_color="off",
            border=True,
        )


def _render_bluestar_chart(snapshots: list) -> None:
    days = [s.day for s in snapshots]
    fig = _styled_fig("Bluestar accumulation")
    fig.add_trace(go.Scatter(
        x=days, y=[s.total_bluestars for s in snapshots],
        mode="lines", name="Bluestars",
        line=dict(color=_BLUE, width=2),
        fill="tozeroy", fillcolor="rgba(37, 99, 235, 0.1)",
    ))
    st.plotly_chart(fig, width="stretch")


def _render_shared_level_chart(snapshots: list, hero_name_map: dict | None = None) -> None:
    """Per-hero level progression over time."""
    if not snapshots or not snapshots[0].hero_levels:
        return
    days = [s.day for s in snapshots]
    hero_ids = list(snapshots[-1].hero_levels.keys())
    hero_name_map = hero_name_map or {}

    fig = _styled_fig("Hero level progression")
    for i, hero_id in enumerate(hero_ids):
        levels = [s.hero_levels.get(hero_id, 1) for s in snapshots]
        display_name = hero_name_map.get(hero_id, hero_id.title())
        fig.add_trace(go.Scatter(
            x=days, y=levels, mode="lines",
            name=display_name, line=dict(color=_HERO_COLORS[i % len(_HERO_COLORS)], width=2),
        ))
    st.plotly_chart(fig, width="stretch")


def _render_hero_card_level_chart(snapshots: list, hero_name_map: dict) -> None:
    if not snapshots or not snapshots[0].hero_card_avg_levels:
        return
    days = [s.day for s in snapshots]
    hero_ids = list(snapshots[-1].hero_card_avg_levels.keys())

    fig = _styled_fig("Average hero card level")
    for i, hero_id in enumerate(hero_ids):
        avgs = [s.hero_card_avg_levels.get(hero_id, 0.0) for s in snapshots]
        display_name = hero_name_map.get(hero_id, hero_id.title())
        fig.add_trace(go.Scatter(
            x=days, y=avgs, mode="lines",
            name=display_name, line=dict(color=_HERO_COLORS[i % len(_HERO_COLORS)], width=2),
        ))
    st.plotly_chart(fig, width="stretch")


def _render_xp_chart(snapshots: list, hero_name_map: dict | None = None) -> None:
    """Stacked bar chart showing per-hero XP earned per day."""
    if not snapshots:
        return
    days = [s.day for s in snapshots]
    hero_name_map = hero_name_map or {}

    # Collect all hero_ids that earned XP at any point
    all_hero_ids: set[str] = set()
    for s in snapshots:
        all_hero_ids.update(s.hero_xp_today.keys())

    if not all_hero_ids:
        # Fallback to total XP bar
        xp = [s.shared_hero_xp_today for s in snapshots]
        fig = _styled_fig("Daily hero XP earned")
        fig.add_trace(go.Bar(x=days, y=xp, name="Total XP", marker_color=_VIOLET, opacity=0.8))
        st.plotly_chart(fig, width="stretch")
        return

    fig = _styled_fig("Daily hero XP earned (per hero)")
    for i, hero_id in enumerate(sorted(all_hero_ids)):
        xp = [s.hero_xp_today.get(hero_id, 0) for s in snapshots]
        display_name = hero_name_map.get(hero_id, hero_id.title())
        fig.add_trace(go.Bar(
            x=days, y=xp, name=display_name,
            marker_color=_HERO_COLORS[i % len(_HERO_COLORS)], opacity=0.8,
        ))
    fig.update_layout(barmode="stack")
    st.plotly_chart(fig, width="stretch")


def _render_chapter_chart(snapshots: list) -> None:
    """Chapters beaten over time + EndOfChapterPack callout (deterministic)."""
    days = [s.day for s in snapshots]
    per_day = [int(getattr(s, "chapters_beaten_today", 0)) for s in snapshots]
    cumulative = [int(getattr(s, "chapters_beaten_total", 0)) for s in snapshots]
    # Fallback in case chapters_beaten_total wasn't populated (older runs):
    if cumulative and cumulative[-1] == 0 and any(per_day):
        running = 0
        cumulative = []
        for c in per_day:
            running += c
            cumulative.append(running)

    eoc_per_day = [
        int(s.pack_counts_by_type.get("EndOfChapterPack", 0)) for s in snapshots
    ]
    eoc_total = sum(eoc_per_day)
    total_chapters = cumulative[-1] if cumulative else 0

    num_days = len(snapshots) or 1
    days_with_chapter = sum(1 for c in per_day if c > 0)

    st.markdown("**Chapter progression**")
    metric_col1, metric_col2, metric_col3 = st.columns(3)
    metric_col1.metric("Chapters beaten", f"{total_chapters:,}")
    metric_col2.metric("EndOfChapterPacks opened", f"{eoc_total:,}")
    metric_col3.metric(
        "Chapters / day (avg)",
        f"{total_chapters / num_days:.2f}",
        delta=f"{days_with_chapter}/{num_days} active days",
        delta_color="off",
        help="Mean chapters beaten per simulated day.",
    )

    fig = _styled_fig("Chapters beaten over time")
    fig.add_trace(go.Bar(
        x=days, y=per_day,
        name="Chapters per day",
        marker_color=_TEAL, opacity=0.55,
    ))
    fig.add_trace(go.Scatter(
        x=days, y=cumulative,
        mode="lines", name="Cumulative chapters",
        line=dict(color=_VIOLET, width=2),
        yaxis="y2",
    ))
    fig.update_layout(
        xaxis=dict(title="Day"),
        yaxis=dict(title="Chapters / day"),
        yaxis2=dict(title="Cumulative chapters", overlaying="y", side="right"),
    )
    st.plotly_chart(fig, width="stretch")

    if eoc_total > 0:
        st.caption(
            "Each chapter beaten opens one EndOfChapterPack. "
            "See the daily pack-mix below for how it stacks against other packs."
        )


def _render_pack_counts_breakdown(snapshots: list) -> None:
    """Stacked daily pack-open counts across all pack types (deterministic).

    Surfaces EndOfChapterPack alongside the other packs so chapter cadence
    is visible in the broader pack mix.
    """
    days = [s.day for s in snapshots]
    pack_names: set[str] = set()
    for s in snapshots:
        pack_names.update(s.pack_counts_by_type.keys())
    if not pack_names:
        return

    fig = _styled_fig("Daily pack opens by type")
    ordered = sorted(pack_names, key=lambda n: (n != "EndOfChapterPack", n))
    for i, name in enumerate(ordered):
        counts = [int(s.pack_counts_by_type.get(name, 0)) for s in snapshots]
        color = _ORANGE if name == "EndOfChapterPack" else _HERO_COLORS[i % len(_HERO_COLORS)]
        fig.add_trace(go.Bar(
            x=days, y=counts, name=name, marker_color=color, opacity=0.85,
        ))
    fig.update_layout(
        barmode="stack",
        xaxis=dict(title="Day"),
        yaxis=dict(title="Packs opened"),
    )
    st.plotly_chart(fig, width="stretch")


def _render_per_hero_breakdown(snapshots: list, hero_name_map: dict | None = None) -> None:
    """Per-hero level / cards / jokers over time (deterministic mode).

    Reads `HeroCardDailySnapshot.hero_states`. Skips if no per-hero data is
    present (e.g. older saved results that pre-date Task 3).
    """
    hero_name_map = hero_name_map or {}
    # Collect hero_ids that have hero_states at any point in the run.
    hero_ids_seen: list[str] = []
    seen_set: set[str] = set()
    for s in snapshots:
        hero_states = getattr(s, "hero_states", None) or {}
        for hid in hero_states:
            if hid not in seen_set:
                seen_set.add(hid)
                hero_ids_seen.append(hid)

    st.markdown("**Per-hero breakdown**")
    if not hero_ids_seen:
        st.caption("No per-hero data in this run.")
        return

    options = hero_ids_seen
    labels = {hid: hero_name_map.get(hid, hid.title()) for hid in options}
    # Default selection: all heroes (caps at the first 4 to keep charts readable).
    default = options if len(options) <= 4 else options[:4]
    selected = st.multiselect(
        "Heroes",
        options=options,
        default=default,
        format_func=lambda hid: labels.get(hid, hid),
        key="variant_b_per_hero_select",
    )
    if not selected:
        st.caption("Select at least one hero to view their breakdown.")
        return

    last = snapshots[-1]
    last_states = getattr(last, "hero_states", None) or {}
    # KPI row — one tile per selected hero with final level / total cards /
    # joker_count. We use st.columns so the metrics sit in a row without
    # cluttering the dashboard's top-of-page KPI strip.
    cols = st.columns(max(1, len(selected)))
    for col, hid in zip(cols, selected):
        snap = last_states.get(hid)
        with col:
            st.markdown(f"**{labels.get(hid, hid)}**")
            if snap is None:
                st.caption("Not yet unlocked.")
                continue
            st.metric("Final level", f"{snap.level}")
            st.metric("Total cards", f"{snap.total_cards:,}")
            st.metric("Jokers", f"{snap.joker_count:,}")

    days = [s.day for s in snapshots]

    # Level over time
    fig_level = _styled_fig("Hero level over time")
    for i, hid in enumerate(selected):
        levels = [
            (getattr(s, "hero_states", None) or {}).get(hid).level
            if (getattr(s, "hero_states", None) or {}).get(hid) is not None
            else None
            for s in snapshots
        ]
        fig_level.add_trace(go.Scatter(
            x=days, y=levels, mode="lines",
            name=labels.get(hid, hid),
            line=dict(color=_HERO_COLORS[options.index(hid) % len(_HERO_COLORS)], width=2),
            connectgaps=False,
        ))
    st.plotly_chart(fig_level, width="stretch")

    # Total cards over time — stacked-by-rarity when one hero is selected,
    # multi-line otherwise (less visual noise than stacking N x 3 traces).
    if len(selected) == 1:
        hid = selected[0]
        rarities_seen: list[str] = []
        rarity_set: set[str] = set()
        for s in snapshots:
            hs = (getattr(s, "hero_states", None) or {}).get(hid)
            if hs is None:
                continue
            for r in hs.cards_by_rarity:
                if r not in rarity_set:
                    rarity_set.add(r)
                    rarities_seen.append(r)
        # Stable order: GOLD, BLUE, GRAY first then anything else.
        rarity_order_pref = ["GOLD", "BLUE", "GRAY"]
        rarities_seen = sorted(
            rarities_seen,
            key=lambda r: (rarity_order_pref.index(r) if r in rarity_order_pref else len(rarity_order_pref), r),
        )
        rarity_color = {"GOLD": _AMBER, "BLUE": _BLUE, "GRAY": "#6B7280"}
        fig_cards = _styled_fig(f"{labels.get(hid, hid)} — cards by rarity")
        for r in rarities_seen:
            counts = [
                ((getattr(s, "hero_states", None) or {}).get(hid).cards_by_rarity.get(r, 0)
                 if (getattr(s, "hero_states", None) or {}).get(hid) is not None else 0)
                for s in snapshots
            ]
            fig_cards.add_trace(go.Bar(
                x=days, y=counts, name=r,
                marker_color=rarity_color.get(r, _VIOLET), opacity=0.85,
            ))
        fig_cards.update_layout(barmode="stack")
        st.plotly_chart(fig_cards, width="stretch")
    else:
        fig_cards = _styled_fig("Total cards over time")
        for hid in selected:
            totals = [
                ((getattr(s, "hero_states", None) or {}).get(hid).total_cards
                 if (getattr(s, "hero_states", None) or {}).get(hid) is not None else None)
                for s in snapshots
            ]
            fig_cards.add_trace(go.Scatter(
                x=days, y=totals, mode="lines",
                name=labels.get(hid, hid),
                line=dict(color=_HERO_COLORS[options.index(hid) % len(_HERO_COLORS)], width=2),
                connectgaps=False,
            ))
        st.plotly_chart(fig_cards, width="stretch")

    # Pet & gear progression per selected hero (Variant B). Only renders when
    # the snapshot type carries pet_level / gear_levels (skipped for old saved
    # results that pre-date Task 4).
    _render_pet_gear_per_hero(snapshots, selected, options, labels)


def _render_hero_token_hunger(
    result: Any, snapshots: list, config: Any, hero_name_map: Dict[str, str],
) -> None:
    """Per-hero Hero Token hunger view — what each hero needs to advance.

    Shows, for every hero, the next skill-tree node, its level + token gate,
    and whether the player's current Hero Token balance covers it. The
    bottom line is a balance/income chart so designers can see at a glance
    whether token inflow is keeping up with the skill-tree demand curve.
    """
    st.markdown("**Hero Token hunger — next skill node per hero**")
    st.caption(
        "Token costs are charged when a hero levels up enough to unlock the "
        "next skill-tree node. Use this view to balance pack/SP token income "
        "against skill-tree cost: anywhere `Needs more` stays > 0 for a long "
        "stretch is a hero whose progression is bottlenecked on tokens."
    )

    balance = int(getattr(result, "final_hero_tokens_balance", 0))
    received = int(getattr(result, "total_hero_tokens", 0))
    spent = int(getattr(result, "total_hero_tokens_spent", 0))
    progress: Dict[str, int] = (
        getattr(result, "final_hero_skill_progress", {}) or {}
    )

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Final token balance", f"{balance:,}")
    k2.metric("Tokens received (run)", f"{received:,}")
    k3.metric("Tokens spent (run)", f"{spent:,}")
    days = max(1, len(snapshots))
    k4.metric("Avg tokens / day", f"{received / days:,.1f}",
              help="Mean tokens received per simulated day.")

    # Per-hero next-node table.
    heroes = list(getattr(config, "heroes", []) or [])
    if not heroes:
        st.caption("No hero definitions in this config.")
        return

    final_levels: Dict[str, int] = getattr(result, "final_hero_levels", {}) or {}

    rows = []
    total_remaining_to_finish = 0
    bottlenecked = 0
    for hero_def in heroes:
        hid = hero_def.hero_id
        name = hero_name_map.get(hid, hid)
        tree = list(getattr(hero_def, "skill_tree", []) or [])
        if not tree:
            continue
        prog = int(progress.get(hid, 0))
        hero_lvl = int(final_levels.get(hid, 1))
        next_idx = prog + 1
        if next_idx >= len(tree):
            rows.append({
                "Hero": name,
                "Hero lvl": hero_lvl,
                "Next node": "MAX",
                "Lvl req": "—",
                "Token cost": "—",
                "Needs more": 0,
                "Status": "✓ Skill tree complete",
            })
            continue
        node = tree[next_idx]
        cost = int(getattr(node, "token_cost", 0) or 0)
        lvl_req = int(getattr(node, "hero_level_required", 0) or 0)
        needs_more = max(0, cost - balance)
        # Remaining tokens to finish the rest of the tree (sum of all
        # untaken nodes' costs).
        remaining_run = sum(
            int(getattr(n, "token_cost", 0) or 0) for n in tree[next_idx:]
        )
        total_remaining_to_finish += remaining_run

        if hero_lvl < lvl_req:
            status = f"⏳ Needs L{lvl_req} (currently L{hero_lvl})"
        elif needs_more > 0:
            status = f"💸 Needs {needs_more:,} more tokens"
            bottlenecked += 1
        else:
            status = "✅ Ready (can buy)"
        rows.append({
            "Hero": name,
            "Hero lvl": hero_lvl,
            "Next node": f"#{node.node_index} · {getattr(node, 'perk_label', '') or '—'}",
            "Lvl req": lvl_req,
            "Token cost": cost,
            "Needs more": needs_more,
            "Status": status,
            "Remaining to finish tree": remaining_run,
        })

    if not rows:
        st.caption("No heroes with skill trees configured.")
        return

    import pandas as pd
    df = pd.DataFrame(rows)
    st.dataframe(df, hide_index=True, width="stretch",
                 height=min(560, 80 + 36 * len(rows)))

    g1, g2 = st.columns(2)
    g1.metric("Heroes bottlenecked on tokens", f"{bottlenecked}",
              help="Hero level met but token balance below next-node cost.")
    g2.metric("Total tokens still needed to fully unlock all trees",
              f"{total_remaining_to_finish:,}",
              delta=f"{total_remaining_to_finish - balance:,} short"
                    if total_remaining_to_finish > balance else "covered",
              delta_color="inverse",
              help="Sum of all untaken skill-tree token costs across heroes vs. current balance.")

    # Token balance / income / spend over time.
    days_axis = [s.day for s in snapshots]
    balance_series = [int(getattr(s, "hero_tokens_balance", 0)) for s in snapshots]
    received_series = [int(getattr(s, "hero_tokens_received", 0)) for s in snapshots]
    spent_series = [int(getattr(s, "hero_tokens_spent_today", 0)) for s in snapshots]

    fig = _styled_fig("Hero Token balance + flow over time")
    fig.add_trace(go.Bar(
        x=days_axis, y=received_series,
        name="Tokens received",
        marker_color=_GREEN, opacity=0.55,
    ))
    fig.add_trace(go.Bar(
        x=days_axis, y=[-v for v in spent_series],
        name="Tokens spent",
        marker_color=_RED, opacity=0.55,
    ))
    fig.add_trace(go.Scatter(
        x=days_axis, y=balance_series,
        mode="lines", name="Balance",
        line=dict(color=_VIOLET, width=2),
        yaxis="y2",
    ))
    fig.update_layout(
        barmode="relative",
        xaxis=dict(title="Day"),
        yaxis=dict(title="Tokens per day"),
        yaxis2=dict(title="Balance", overlaying="y", side="right"),
    )
    st.plotly_chart(fig, width="stretch")


def _render_pet_gear_per_hero(
    snapshots: list, selected: list, options: list, labels: dict
) -> None:
    """Per-hero pet level + gear total level over time (deterministic)."""
    if not snapshots:
        return
    # Probe one snapshot to confirm pet/gear fields are available.
    sample = None
    for s in snapshots:
        states = getattr(s, "hero_states", None) or {}
        if states:
            sample = next(iter(states.values()))
            break
    if sample is None or not hasattr(sample, "pet_level"):
        return

    days = [s.day for s in snapshots]

    fig_pet = _styled_fig("Pet level over time")
    for hid in selected:
        series = [
            (
                (getattr(s, "hero_states", None) or {}).get(hid).pet_level
                if (getattr(s, "hero_states", None) or {}).get(hid) is not None
                else None
            )
            for s in snapshots
        ]
        fig_pet.add_trace(go.Scatter(
            x=days, y=series, mode="lines",
            name=labels.get(hid, hid),
            line=dict(color=_HERO_COLORS[options.index(hid) % len(_HERO_COLORS)], width=2),
            connectgaps=False,
        ))
    st.plotly_chart(fig_pet, width="stretch")

    fig_gear = _styled_fig("Gear total level over time")
    for hid in selected:
        series = [
            (
                (getattr(s, "hero_states", None) or {}).get(hid).gear_total_level
                if (getattr(s, "hero_states", None) or {}).get(hid) is not None
                else None
            )
            for s in snapshots
        ]
        fig_gear.add_trace(go.Scatter(
            x=days, y=series, mode="lines",
            name=labels.get(hid, hid),
            line=dict(color=_HERO_COLORS[options.index(hid) % len(_HERO_COLORS)], width=2),
            connectgaps=False,
        ))
    st.plotly_chart(fig_gear, width="stretch")

    # Per-slot gear breakdown when a single hero is selected — line per slot.
    if len(selected) == 1:
        hid = selected[0]
        # Find slots seen across the run.
        slot_set: set[str] = set()
        for s in snapshots:
            hs = (getattr(s, "hero_states", None) or {}).get(hid)
            if hs is None:
                continue
            slot_set.update(hs.gear_levels.keys())
        if slot_set:
            fig_slots = _styled_fig(f"{labels.get(hid, hid)} — gear by slot")
            for i, slot in enumerate(sorted(slot_set)):
                series = [
                    (
                        (getattr(s, "hero_states", None) or {}).get(hid).gear_levels.get(slot, 1)
                        if (getattr(s, "hero_states", None) or {}).get(hid) is not None
                        else None
                    )
                    for s in snapshots
                ]
                fig_slots.add_trace(go.Scatter(
                    x=days, y=series, mode="lines",
                    name=slot,
                    line=dict(color=_HERO_COLORS[i % len(_HERO_COLORS)], width=2),
                    connectgaps=False,
                ))
            st.plotly_chart(fig_slots, width="stretch")


def _render_mc_per_hero_breakdown(result: Any) -> None:
    """Per-hero mean-level chart with 95% CI band (Monte Carlo mode)."""
    means = getattr(result, "daily_hero_level_means", {}) or {}
    stds = getattr(result, "daily_hero_level_stds", {}) or {}
    if not means:
        return

    hero_ids = list(means.keys())
    config = st.session_state.get("config")
    hero_name_map: Dict[str, str] = {}
    if config and hasattr(config, "heroes"):
        hero_name_map = {h.hero_id: h.name for h in config.heroes}
    labels = {hid: hero_name_map.get(hid, hid.title()) for hid in hero_ids}

    st.markdown("**Per-hero breakdown (Monte Carlo)**")
    default = hero_ids if len(hero_ids) <= 4 else hero_ids[:4]
    selected = st.multiselect(
        "Heroes",
        options=hero_ids,
        default=default,
        format_func=lambda hid: labels.get(hid, hid),
        key="variant_b_per_hero_mc_select",
    )
    if not selected:
        st.caption("Select at least one hero to view per-hero MC means.")
        return

    # Final-day means table.
    cols = st.columns(max(1, len(selected)))
    cards_means = getattr(result, "daily_hero_total_cards_means", {}) or {}
    joker_means = getattr(result, "daily_hero_joker_means", {}) or {}
    for col, hid in zip(cols, selected):
        with col:
            st.markdown(f"**{labels.get(hid, hid)}**")
            lvl_series = means.get(hid, [])
            std_series = stds.get(hid, [])
            cards_series = cards_means.get(hid, [])
            joker_series = joker_means.get(hid, [])
            final_lvl = lvl_series[-1] if lvl_series else 0.0
            final_std = std_series[-1] if std_series else 0.0
            st.metric("Mean final level", f"{final_lvl:.1f} +/- {final_std:.1f}")
            if cards_series:
                st.metric("Mean total cards", f"{cards_series[-1]:,.0f}")
            if joker_series:
                st.metric("Mean jokers", f"{joker_series[-1]:,.1f}")

    fig = _styled_fig("Hero level over time (Monte Carlo)")
    for i, hid in enumerate(selected):
        lvl_series = means.get(hid, [])
        std_series = stds.get(hid, [0.0] * len(lvl_series))
        days = list(range(1, len(lvl_series) + 1))
        color = _HERO_COLORS[hero_ids.index(hid) % len(_HERO_COLORS)]
        # 95% CI ribbon
        upper = [m + 1.96 * s for m, s in zip(lvl_series, std_series)]
        lower = [max(0.0, m - 1.96 * s) for m, s in zip(lvl_series, std_series)]
        # Plotly fillcolor needs rgba; we just use a translucent grey since
        # adding a per-hero rgba conversion is overkill for the use case.
        fig.add_trace(go.Scatter(
            x=days + days[::-1], y=upper + lower[::-1],
            fill="toself", fillcolor="rgba(120, 120, 120, 0.10)",
            line=dict(color="rgba(255,255,255,0)"),
            name=f"{labels.get(hid, hid)} 95% CI",
            hoverinfo="skip", showlegend=False,
        ))
        fig.add_trace(go.Scatter(
            x=days, y=lvl_series, mode="lines",
            name=labels.get(hid, hid),
            line=dict(color=color, width=2),
        ))
    st.plotly_chart(fig, width="stretch")

    # Pet level (mean line + 95% CI). Gear is summarized as a single
    # "total level" metric to avoid charting N hero x M slot lines.
    pet_means = getattr(result, "daily_hero_pet_level_means", {}) or {}
    pet_stds = getattr(result, "daily_hero_pet_level_stds", {}) or {}
    if pet_means:
        fig_pet = _styled_fig("Pet level over time (Monte Carlo)")
        for hid in selected:
            series = pet_means.get(hid, [])
            std_series = pet_stds.get(hid, [0.0] * len(series))
            if not series:
                continue
            days = list(range(1, len(series) + 1))
            color = _HERO_COLORS[hero_ids.index(hid) % len(_HERO_COLORS)]
            upper = [m + 1.96 * s for m, s in zip(series, std_series)]
            lower = [max(0.0, m - 1.96 * s) for m, s in zip(series, std_series)]
            fig_pet.add_trace(go.Scatter(
                x=days + days[::-1], y=upper + lower[::-1],
                fill="toself", fillcolor="rgba(120, 120, 120, 0.10)",
                line=dict(color="rgba(255,255,255,0)"),
                name=f"{labels.get(hid, hid)} 95% CI",
                hoverinfo="skip", showlegend=False,
            ))
            fig_pet.add_trace(go.Scatter(
                x=days, y=series, mode="lines",
                name=labels.get(hid, hid),
                line=dict(color=color, width=2),
            ))
        st.plotly_chart(fig_pet, width="stretch")

    gear_means = getattr(result, "daily_hero_gear_total_level_means", {}) or {}
    if gear_means:
        fig_gear = _styled_fig("Gear total level over time (Monte Carlo)")
        for hid in selected:
            series = gear_means.get(hid, [])
            if not series:
                continue
            days = list(range(1, len(series) + 1))
            color = _HERO_COLORS[hero_ids.index(hid) % len(_HERO_COLORS)]
            fig_gear.add_trace(go.Scatter(
                x=days, y=series, mode="lines",
                name=labels.get(hid, hid),
                line=dict(color=color, width=2),
            ))
        st.plotly_chart(fig_gear, width="stretch")


def _render_mc_chapter_chart(result: Any) -> None:
    """MC-aggregated chapters beaten per day (derived from EoC pack counts).

    Per chapter-cadence rule (orchestrator.py), each chapter beaten opens
    exactly one EndOfChapterPack, so daily EoC pack means == mean chapters
    beaten per day. The simulation engine doesn't aggregate
    chapters_beaten_today directly, so we reuse the pack accumulators.
    """
    means_by_pack = getattr(result, "daily_pack_count_means", {}) or {}
    stds_by_pack = getattr(result, "daily_pack_count_stds", {}) or {}
    daily_means = means_by_pack.get("EndOfChapterPack")
    if not daily_means:
        return

    daily_stds = stds_by_pack.get("EndOfChapterPack", [0.0] * len(daily_means))
    days = list(range(1, len(daily_means) + 1))
    cumulative = []
    running = 0.0
    for m in daily_means:
        running += float(m)
        cumulative.append(running)

    mean_total_chapters = cumulative[-1] if cumulative else 0.0

    with st.container(horizontal=True):
        st.metric(
            "Mean chapters beaten",
            f"{mean_total_chapters:,.1f}",
            border=True,
        )
        st.metric(
            "Mean EndOfChapterPacks / run",
            f"{mean_total_chapters:,.1f}",
            border=True,
        )

    fig = _styled_fig("Chapters beaten over time (Monte Carlo)")
    upper = [m + 1.96 * s for m, s in zip(daily_means, daily_stds)]
    lower = [max(0.0, m - 1.96 * s) for m, s in zip(daily_means, daily_stds)]
    fig.add_trace(go.Scatter(
        x=days + days[::-1], y=upper + lower[::-1],
        fill="toself", fillcolor="rgba(13, 148, 178, 0.12)",
        line=dict(color="rgba(255,255,255,0)"),
        name="Per-day 95% CI",
        hoverinfo="skip",
    ))
    fig.add_trace(go.Bar(
        x=days, y=daily_means,
        name="Mean chapters / day",
        marker_color=_TEAL, opacity=0.55,
    ))
    fig.add_trace(go.Scatter(
        x=days, y=cumulative,
        mode="lines", name="Cumulative (mean)",
        line=dict(color=_VIOLET, width=2),
        yaxis="y2",
    ))
    fig.update_layout(
        xaxis=dict(title="Day"),
        yaxis=dict(title="Chapters / day"),
        yaxis2=dict(title="Cumulative chapters", overlaying="y", side="right"),
    )
    st.plotly_chart(fig, width="stretch")
    st.caption(
        "Each chapter beaten opens one EndOfChapterPack — daily means are "
        "derived from the EndOfChapterPack accumulator."
    )


def _render_coin_chart(snapshots: list) -> None:
    days = [s.day for s in snapshots]
    fig = _styled_fig("Coin economy")
    fig.add_trace(go.Scatter(
        x=days, y=[s.coins_earned_today for s in snapshots],
        fill="tozeroy", name="Income",
        line=dict(color=_GREEN), fillcolor="rgba(22, 163, 74, 0.1)",
    ))
    fig.add_trace(go.Scatter(
        x=days, y=[s.coins_spent_today for s in snapshots],
        fill="tozeroy", name="Spending",
        line=dict(color=_RED), fillcolor="rgba(220, 38, 38, 0.1)",
    ))
    fig.add_trace(go.Scatter(
        x=days, y=[s.coins_balance for s in snapshots],
        mode="lines", name="Balance",
        line=dict(color=_AMBER, width=2),
    ))
    st.plotly_chart(fig, width="stretch")


def _render_premium_pack_summary(result: Any, snapshots: list) -> None:
    with st.container(border=True):
        st.markdown("**Premium packs**")
        total_packs = sum(s.premium_packs_opened for s in snapshots)
        total_diamonds = result.total_premium_diamonds_spent
        st.metric("Packs opened", f"{total_packs:,}")
        st.metric("Diamonds spent", f"{total_diamonds:,}")
        st.metric("Avg diamond/pack", f"{total_diamonds / max(1, total_packs):,.0f}")


def _render_joker_summary(snapshots: list) -> None:
    with st.container(border=True):
        st.markdown("**Hero jokers**")
        total_received = sum(s.jokers_received_today for s in snapshots)
        total_used = sum(s.jokers_used_today for s in snapshots)
        st.metric("Received", f"{total_received:,}")
        st.metric("Used", f"{total_used:,}")
        st.metric("Remaining", f"{total_received - total_used:,}")


def _render_skill_tree_summary(snapshots: list) -> None:
    with st.container(border=True):
        st.markdown("**Skill tree progress**")
        total_nodes: Dict[str, int] = {}
        total_cards = sum(s.cards_unlocked_today for s in snapshots)
        for s in snapshots:
            for hero_id, count in s.skill_nodes_unlocked_today.items():
                total_nodes[hero_id] = total_nodes.get(hero_id, 0) + count

        total_node_count = sum(total_nodes.values())
        st.metric("Nodes unlocked", f"{total_node_count:,}")
        st.metric("Cards unlocked", f"{total_cards:,}")
        if total_nodes:
            st.caption(f"Across {len(total_nodes)} heroes")


def _render_save_popover(result: Any, mode: str) -> None:
    """Save the current Hero Card System result to disk (mirrors variant A dashboard)."""
    if mode == "deterministic":
        default_name = f"HeroCard_det_{getattr(result, 'total_bluestars', 0)}"
    else:
        default_name = "HeroCard_MC"
    with st.popover("Save result", icon=":material/bookmark:"):
        save_name = st.text_input("Name", value=default_name, key="vb_save_name")
        save_desc = st.text_area("Description (optional)", height=68, key="vb_save_desc")
        if st.button("Save", width="stretch", icon=":material/save:", type="primary", key="vb_save_btn"):
            try:
                from app_pages.results_manager import save_current_result
                filename = save_current_result(save_name, save_desc)
                st.success(f"Saved as {filename}!", icon=":material/check_circle:")
            except Exception as e:
                st.error(f"Failed to save: {e}")


def _render_mc_summary(result: Any) -> None:
    mean, std = result.bluestar_stats.result()
    with st.container(horizontal=True):
        st.metric("Mean final bluestars", f"{mean:,.0f} +/- {std:,.0f}", border=True)
        st.metric("MC runs", f"{result.num_runs}", border=True)
        st.metric("Completion time", f"{result.completion_time:.1f}s", border=True)


def _render_mc_bluestar_chart(result: Any) -> None:
    means = result.daily_bluestar_means
    stds = result.daily_bluestar_stds
    days = list(range(1, len(means) + 1))

    fig = _styled_fig("Bluestar accumulation (Monte Carlo)")
    upper = [m + 1.96 * s for m, s in zip(means, stds)]
    lower = [m - 1.96 * s for m, s in zip(means, stds)]
    fig.add_trace(go.Scatter(
        x=days + days[::-1], y=upper + lower[::-1],
        fill="toself", fillcolor="rgba(37, 99, 235, 0.12)",
        line=dict(color="rgba(255,255,255,0)"), name="95% CI",
    ))
    fig.add_trace(go.Scatter(
        x=days, y=means, mode="lines", name="Mean bluestars",
        line=dict(color=_BLUE, width=2),
    ))
    st.plotly_chart(fig, width="stretch")
