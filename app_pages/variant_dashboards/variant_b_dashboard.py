"""Variant B dashboard — Hero Card System.

Displays hero progression, card levels, skill tree progress,
premium economics, and standard bluestar/coin charts.
"""

from typing import Any, Dict

import plotly.graph_objects as go
import streamlit as st

# Chart template matching the dark theme
_CHART_TEMPLATE = "plotly_dark"
_CHART_BG = "rgba(0,0,0,0)"
_GRID_COLOR = "rgba(255,255,255,0.06)"

# Palette
_BLUE = "#38BDF8"
_GREEN = "#34D399"
_AMBER = "#FBBF24"
_RED = "#F87171"
_VIOLET = "#A78BFA"
_ORANGE = "#FB923C"
_TEAL = "#2DD4BF"
_PINK = "#E879F9"
_HERO_COLORS = [_BLUE, _GREEN, _AMBER, _RED, _VIOLET, _ORANGE, _TEAL, _PINK,
                "#67E8F9", "#86EFAC", "#FDE68A", "#FCA5A5", "#C4B5FD", "#FDBA74", "#5EEAD4", "#F0ABFC"]


def _styled_fig(title: str = "") -> go.Figure:
    """Create a pre-styled Plotly figure matching the dark theme."""
    fig = go.Figure()
    fig.update_layout(
        title=dict(text=title, font=dict(size=16)),
        template=_CHART_TEMPLATE,
        paper_bgcolor=_CHART_BG,
        plot_bgcolor=_CHART_BG,
        xaxis=dict(gridcolor=_GRID_COLOR, zeroline=False),
        yaxis=dict(gridcolor=_GRID_COLOR, zeroline=False),
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

    if mode != "deterministic":
        _render_mc_summary(result)
        _render_mc_bluestar_chart(result)
        return

    snapshots = result.daily_snapshots
    if not snapshots:
        st.info("No data in simulation results.", icon=":material/info:")
        return

    # ─── KPI row ──────────────────────────────────────────────────────────────
    _render_kpis(result, snapshots)

    # ─── Charts in a 2-column grid ────────────────────────────────────────────
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
            _render_hero_level_chart(snapshots)
    with col4:
        with st.container(border=True):
            _render_hero_card_level_chart(snapshots)

    with st.container(border=True):
        _render_xp_chart(snapshots)

    # ─── Summary sections ─────────────────────────────────────────────────────
    col5, col6, col7 = st.columns(3)
    with col5:
        _render_premium_pack_summary(result, snapshots)
    with col6:
        _render_joker_summary(snapshots)
    with col7:
        _render_skill_tree_summary(snapshots)


def _render_kpis(result: Any, snapshots: list) -> None:
    with st.container(horizontal=True):
        st.metric("Total bluestars", f"{result.total_bluestars:,}", border=True)
        st.metric("Coins earned", f"{result.total_coins_earned:,}", border=True)
        st.metric("Total upgrades", f"{sum(result.total_upgrades.values()):,}", border=True)
        st.metric("Jokers received", f"{result.total_jokers_received:,}", border=True)
        st.metric("Diamonds spent", f"{result.total_premium_diamonds_spent:,}", border=True)

    # Hero level badges
    if result.final_hero_levels:
        with st.expander(f"Final hero levels ({len(result.final_hero_levels)} heroes)", icon=":material/person:"):
            # Show in rows of 6
            hero_items = list(result.final_hero_levels.items())
            for row_start in range(0, len(hero_items), 6):
                row = hero_items[row_start:row_start + 6]
                cols = st.columns(len(row))
                for i, (hero_id, level) in enumerate(row):
                    cols[i].metric(hero_id, f"Lv {level}", border=True)


def _render_bluestar_chart(snapshots: list) -> None:
    days = [s.day for s in snapshots]
    fig = _styled_fig("Bluestar accumulation")
    fig.add_trace(go.Scatter(
        x=days, y=[s.total_bluestars for s in snapshots],
        mode="lines", name="Bluestars",
        line=dict(color=_BLUE, width=2),
        fill="tozeroy", fillcolor="rgba(56, 189, 248, 0.08)",
    ))
    st.plotly_chart(fig, use_container_width=True)


def _render_hero_level_chart(snapshots: list) -> None:
    if not snapshots or not snapshots[0].hero_levels:
        return
    days = [s.day for s in snapshots]
    hero_ids = list(snapshots[-1].hero_levels.keys())

    fig = _styled_fig("Hero level progression")
    for i, hero_id in enumerate(hero_ids):
        levels = [s.hero_levels.get(hero_id, 0) for s in snapshots]
        fig.add_trace(go.Scatter(
            x=days, y=levels, mode="lines",
            name=hero_id, line=dict(color=_HERO_COLORS[i % len(_HERO_COLORS)], width=2),
        ))
    st.plotly_chart(fig, use_container_width=True)


def _render_hero_card_level_chart(snapshots: list) -> None:
    if not snapshots or not snapshots[0].hero_card_avg_levels:
        return
    days = [s.day for s in snapshots]
    hero_ids = list(snapshots[-1].hero_card_avg_levels.keys())

    fig = _styled_fig("Average hero card level")
    for i, hero_id in enumerate(hero_ids):
        avgs = [s.hero_card_avg_levels.get(hero_id, 0.0) for s in snapshots]
        fig.add_trace(go.Scatter(
            x=days, y=avgs, mode="lines",
            name=hero_id, line=dict(color=_HERO_COLORS[i % len(_HERO_COLORS)], width=2),
        ))
    st.plotly_chart(fig, use_container_width=True)


def _render_xp_chart(snapshots: list) -> None:
    if not snapshots or not snapshots[0].hero_xp_today:
        return
    days = [s.day for s in snapshots]
    hero_ids = sorted(set(h for s in snapshots for h in s.hero_xp_today.keys()))

    fig = _styled_fig("Daily hero XP earned")
    for i, hero_id in enumerate(hero_ids):
        xp = [s.hero_xp_today.get(hero_id, 0) for s in snapshots]
        fig.add_trace(go.Bar(
            x=days, y=xp, name=hero_id,
            marker_color=_HERO_COLORS[i % len(_HERO_COLORS)], opacity=0.8,
        ))
    fig.update_layout(barmode="group")
    st.plotly_chart(fig, use_container_width=True)


def _render_coin_chart(snapshots: list) -> None:
    days = [s.day for s in snapshots]
    fig = _styled_fig("Coin economy")
    fig.add_trace(go.Scatter(
        x=days, y=[s.coins_earned_today for s in snapshots],
        fill="tozeroy", name="Income",
        line=dict(color=_GREEN), fillcolor="rgba(52, 211, 153, 0.15)",
    ))
    fig.add_trace(go.Scatter(
        x=days, y=[s.coins_spent_today for s in snapshots],
        fill="tozeroy", name="Spending",
        line=dict(color=_RED), fillcolor="rgba(248, 113, 113, 0.15)",
    ))
    fig.add_trace(go.Scatter(
        x=days, y=[s.coins_balance for s in snapshots],
        mode="lines", name="Balance",
        line=dict(color=_AMBER, width=2),
    ))
    st.plotly_chart(fig, use_container_width=True)


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
        fill="toself", fillcolor="rgba(56, 189, 248, 0.12)",
        line=dict(color="rgba(255,255,255,0)"), name="95% CI",
    ))
    fig.add_trace(go.Scatter(
        x=days, y=means, mode="lines", name="Mean bluestars",
        line=dict(color=_BLUE, width=2),
    ))
    st.plotly_chart(fig, use_container_width=True)
