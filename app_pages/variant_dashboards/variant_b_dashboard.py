"""Variant B dashboard — Hero Card System.

Displays hero XP progression, per-hero card levels, skill tree progress,
premium pack economics, and standard bluestar/coin charts.
"""

from typing import Any, Dict, List

import plotly.graph_objects as go
import streamlit as st


def render_variant_b_dashboard() -> None:
    if "sim_result" not in st.session_state:
        st.warning("No simulation results. Run a simulation first.")
        return

    result = st.session_state.sim_result
    mode = st.session_state.get("sim_mode", "deterministic")

    st.title("Hero Card System Dashboard")

    if mode != "deterministic":
        _render_mc_summary(result)
        _render_mc_bluestar_chart(result)
        return

    snapshots = result.daily_snapshots
    if not snapshots:
        st.warning("No data in simulation results.")
        return

    # KPI row
    _render_kpis(result, snapshots)
    st.divider()

    # Charts
    _render_bluestar_chart(snapshots)
    _render_hero_level_chart(snapshots)
    _render_hero_card_level_chart(snapshots)
    _render_xp_chart(snapshots)
    _render_coin_chart(snapshots)

    st.divider()
    _render_premium_pack_summary(result, snapshots)
    _render_joker_summary(snapshots)
    _render_skill_tree_summary(snapshots)


def _render_kpis(result: Any, snapshots: list) -> None:
    cols = st.columns(5)
    cols[0].metric("Total Bluestars", f"{result.total_bluestars:,}")
    cols[1].metric("Coins Earned", f"{result.total_coins_earned:,}")
    cols[2].metric("Total Upgrades", f"{sum(result.total_upgrades.values()):,}")
    cols[3].metric("Jokers Received", f"{result.total_jokers_received:,}")
    cols[4].metric("Diamonds Spent (Premium)", f"{result.total_premium_diamonds_spent:,}")

    # Hero levels
    if result.final_hero_levels:
        st.markdown("**Final Hero Levels**")
        hero_cols = st.columns(len(result.final_hero_levels))
        for i, (hero_id, level) in enumerate(result.final_hero_levels.items()):
            hero_cols[i].metric(hero_id, f"Lv {level}")


def _render_bluestar_chart(snapshots: list) -> None:
    days = [s.day for s in snapshots]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=days, y=[s.total_bluestars for s in snapshots],
        mode="lines", name="Total Bluestars",
        line=dict(color="#1f77b4", width=2),
    ))
    fig.update_layout(
        title="Bluestar Accumulation",
        xaxis=dict(title="Day"), yaxis=dict(title="Bluestars"),
        template="plotly_white", hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_hero_level_chart(snapshots: list) -> None:
    if not snapshots or not snapshots[0].hero_levels:
        return
    days = [s.day for s in snapshots]
    hero_ids = list(snapshots[-1].hero_levels.keys())
    colors = ["#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]

    fig = go.Figure()
    for i, hero_id in enumerate(hero_ids):
        levels = [s.hero_levels.get(hero_id, 0) for s in snapshots]
        fig.add_trace(go.Scatter(
            x=days, y=levels, mode="lines+markers",
            name=hero_id, line=dict(color=colors[i % len(colors)], width=2),
            marker=dict(size=3),
        ))
    fig.update_layout(
        title="Hero Level Progression",
        xaxis=dict(title="Day"), yaxis=dict(title="Hero Level"),
        template="plotly_white", hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_hero_card_level_chart(snapshots: list) -> None:
    if not snapshots or not snapshots[0].hero_card_avg_levels:
        return
    days = [s.day for s in snapshots]
    hero_ids = list(snapshots[-1].hero_card_avg_levels.keys())
    colors = ["#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]

    fig = go.Figure()
    for i, hero_id in enumerate(hero_ids):
        avgs = [s.hero_card_avg_levels.get(hero_id, 0.0) for s in snapshots]
        fig.add_trace(go.Scatter(
            x=days, y=avgs, mode="lines",
            name=f"{hero_id} avg card level",
            line=dict(color=colors[i % len(colors)], width=2),
        ))
    fig.update_layout(
        title="Average Hero Card Level",
        xaxis=dict(title="Day"), yaxis=dict(title="Avg Card Level"),
        template="plotly_white", hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_xp_chart(snapshots: list) -> None:
    if not snapshots or not snapshots[0].hero_xp_today:
        return
    days = [s.day for s in snapshots]
    hero_ids = sorted(set(h for s in snapshots for h in s.hero_xp_today.keys()))
    colors = ["#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]

    fig = go.Figure()
    for i, hero_id in enumerate(hero_ids):
        xp = [s.hero_xp_today.get(hero_id, 0) for s in snapshots]
        fig.add_trace(go.Bar(
            x=days, y=xp, name=f"{hero_id} XP",
            marker_color=colors[i % len(colors)], opacity=0.7,
        ))
    fig.update_layout(
        title="Daily Hero XP Earned",
        xaxis=dict(title="Day"), yaxis=dict(title="XP"),
        barmode="group", template="plotly_white",
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_coin_chart(snapshots: list) -> None:
    days = [s.day for s in snapshots]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=days, y=[s.coins_earned_today for s in snapshots],
        fill="tozeroy", name="Income", line=dict(color="green"),
    ))
    fig.add_trace(go.Scatter(
        x=days, y=[s.coins_spent_today for s in snapshots],
        fill="tozeroy", name="Spending", line=dict(color="red"),
    ))
    fig.add_trace(go.Scatter(
        x=days, y=[s.coins_balance for s in snapshots],
        mode="lines", name="Balance", line=dict(color="blue", width=2),
    ))
    fig.update_layout(
        title="Coin Economy",
        xaxis=dict(title="Day"), yaxis=dict(title="Coins"),
        template="plotly_white", hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_premium_pack_summary(result: Any, snapshots: list) -> None:
    st.subheader("Premium Pack Economics")
    total_packs = sum(s.premium_packs_opened for s in snapshots)
    total_diamonds = result.total_premium_diamonds_spent
    col1, col2, col3 = st.columns(3)
    col1.metric("Premium Packs Opened", f"{total_packs:,}")
    col2.metric("Diamonds Spent", f"{total_diamonds:,}")
    col3.metric("Avg Diamond/Pack", f"{total_diamonds / max(1, total_packs):,.0f}")


def _render_joker_summary(snapshots: list) -> None:
    st.subheader("Hero Joker Summary")
    total_received = sum(s.jokers_received_today for s in snapshots)
    total_used = sum(s.jokers_used_today for s in snapshots)
    col1, col2, col3 = st.columns(3)
    col1.metric("Jokers Received", f"{total_received:,}")
    col2.metric("Jokers Used", f"{total_used:,}")
    col3.metric("Jokers Remaining", f"{total_received - total_used:,}")


def _render_skill_tree_summary(snapshots: list) -> None:
    st.subheader("Skill Tree Progress")
    total_nodes: Dict[str, int] = {}
    total_cards = sum(s.cards_unlocked_today for s in snapshots)
    for s in snapshots:
        for hero_id, count in s.skill_nodes_unlocked_today.items():
            total_nodes[hero_id] = total_nodes.get(hero_id, 0) + count

    if total_nodes:
        cols = st.columns(len(total_nodes) + 1)
        for i, (hero_id, nodes) in enumerate(total_nodes.items()):
            cols[i].metric(f"{hero_id} Nodes", nodes)
        cols[-1].metric("Cards Unlocked", total_cards)
    else:
        st.info("No skill tree nodes were unlocked during this simulation.")


def _render_mc_summary(result: Any) -> None:
    mean, std = result.bluestar_stats.result()
    cols = st.columns(3)
    cols[0].metric("Mean Final Bluestars", f"{mean:,.0f} ± {std:,.0f}")
    cols[1].metric("MC Runs", f"{result.num_runs}")
    cols[2].metric("Completion Time", f"{result.completion_time:.1f}s")


def _render_mc_bluestar_chart(result: Any) -> None:
    means = result.daily_bluestar_means
    stds = result.daily_bluestar_stds
    days = list(range(1, len(means) + 1))

    fig = go.Figure()
    upper = [m + 1.96 * s for m, s in zip(means, stds)]
    lower = [m - 1.96 * s for m, s in zip(means, stds)]
    fig.add_trace(go.Scatter(
        x=days + days[::-1], y=upper + lower[::-1],
        fill="toself", fillcolor="rgba(31, 119, 180, 0.2)",
        line=dict(color="rgba(255,255,255,0)"), name="95% CI",
    ))
    fig.add_trace(go.Scatter(
        x=days, y=means, mode="lines", name="Mean Bluestars",
        line=dict(color="#1f77b4", width=2),
    ))
    fig.update_layout(
        title="Bluestar Accumulation (Monte Carlo)",
        xaxis=dict(title="Day"), yaxis=dict(title="Total Bluestars"),
        template="plotly_white", hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)
