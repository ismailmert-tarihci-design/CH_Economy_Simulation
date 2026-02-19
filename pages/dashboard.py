"""Dashboard with interactive Plotly charts for simulation results."""

from typing import Any

import plotly.graph_objects as go
import streamlit as st

from pages.dashboard_charts import (
    add_category_ci,
    add_coin_balance_ci,
    render_kpi_row,
    render_pack_counts_chart,
    render_pull_counts_chart,
    render_unique_unlocked_chart,
    render_upgrades_chart,
)


def render_dashboard() -> None:
    if "sim_result" not in st.session_state:
        st.warning("No simulation results available. Run a simulation first.")
        return

    result = st.session_state.sim_result
    mode = st.session_state.sim_mode

    st.title("Simulation Dashboard")

    render_kpi_row(result, mode)
    st.divider()
    _render_bluestar_chart(result, mode)
    _render_card_progression_chart(result, mode)
    if mode == "deterministic":
        _render_upgrades_and_unlocked(result)
    _render_coin_flow_chart(result, mode)
    st.divider()
    render_pull_counts_chart(result, mode)
    render_pack_counts_chart(result, mode)


def _render_upgrades_and_unlocked(result: Any) -> None:
    render_upgrades_chart(result)
    render_unique_unlocked_chart(result)


def _render_bluestar_chart(result: Any, mode: str) -> None:
    """Chart 1: Bluestar accumulation over time."""
    fig = go.Figure()
    if mode == "deterministic":
        snapshots = result.daily_snapshots
        days = list(range(1, len(snapshots) + 1))
        bluestars = [snapshot.total_bluestars for snapshot in snapshots]
        fig.add_trace(
            go.Scatter(
                x=days,
                y=bluestars,
                mode="lines",
                name="Total Bluestars",
                line=dict(color="rgb(31, 119, 180)", width=2),
            )
        )
    else:
        means = result.daily_bluestar_means
        stds = result.daily_bluestar_stds
        days = list(range(1, len(means) + 1))
        upper = [m + 1.96 * s for m, s in zip(means, stds)]
        lower = [m - 1.96 * s for m, s in zip(means, stds)]
        x_combined = days + days[::-1]
        y_combined = upper + lower[::-1]
        fig.add_trace(
            go.Scatter(
                x=x_combined,
                y=y_combined,
                fill="toself",
                fillcolor="rgba(31, 119, 180, 0.2)",
                line=dict(color="rgba(255,255,255,0)"),
                name="95% CI",
                showlegend=True,
                hoverinfo="skip",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=days,
                y=means,
                mode="lines",
                name="Mean Bluestars",
                line=dict(color="rgb(31, 119, 180)", width=2),
            )
        )
    fig.update_layout(
        title="Bluestar Accumulation Over Time",
        xaxis=dict(title="Day"),
        yaxis=dict(title="Total Bluestars"),
        hovermode="x unified",
        template="plotly_white",
    )
    st.plotly_chart(fig, width="stretch")


def _render_card_progression_chart(result: Any, mode: str) -> None:
    """Chart 2: Average card level by category."""
    fig = go.Figure()
    COLORS = {"GOLD_SHARED": "#FFD700", "BLUE_SHARED": "#4169E1", "UNIQUE": "#FF4500"}
    DISPLAY_NAMES = {
        "GOLD_SHARED": "Gold Shared",
        "BLUE_SHARED": "Blue Shared",
        "UNIQUE": "Unique",
    }
    if mode == "deterministic":
        snapshots = result.daily_snapshots
        days = list(range(1, len(snapshots) + 1))
        category_data = {"GOLD_SHARED": [], "BLUE_SHARED": [], "UNIQUE": []}
        for snapshot in snapshots:
            for category in category_data.keys():
                category_data[category].append(
                    snapshot.category_avg_levels.get(category, 0.0)
                )
        for category in ["GOLD_SHARED", "BLUE_SHARED", "UNIQUE"]:
            fig.add_trace(
                go.Scatter(
                    x=days,
                    y=category_data[category],
                    mode="lines",
                    name=DISPLAY_NAMES[category],
                    line=dict(color=COLORS[category], width=2),
                )
            )
    else:
        means_by_category = result.daily_category_level_means
        num_days = len(next(iter(means_by_category.values())))
        days = list(range(1, num_days + 1))
        for category in ["GOLD_SHARED", "BLUE_SHARED", "UNIQUE"]:
            if category in means_by_category:
                fig.add_trace(
                    go.Scatter(
                        x=days,
                        y=means_by_category[category],
                        mode="lines",
                        name=DISPLAY_NAMES[category],
                        line=dict(color=COLORS[category], width=2),
                    )
                )
        add_category_ci(fig, result)
    max_day = days[-1]
    fig.add_trace(
        go.Scatter(
            x=[1, max_day],
            y=[100, 100],
            mode="lines",
            name="Shared Max (100)",
            line=dict(color="gray", width=1, dash="dash"),
            showlegend=True,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[1, max_day],
            y=[10, 10],
            mode="lines",
            name="Unique Max (10)",
            line=dict(color="darkgray", width=1, dash="dash"),
            showlegend=True,
        )
    )
    fig.update_layout(
        title="Average Card Level by Category",
        xaxis=dict(title="Day"),
        yaxis=dict(title="Average Card Level"),
        hovermode="x unified",
        template="plotly_white",
    )
    st.plotly_chart(fig, width="stretch")


def _render_coin_flow_chart(result: Any, mode: str) -> None:
    """Chart 3: Coin economy income, spending, and balance over time."""
    fig = go.Figure()
    if mode == "deterministic":
        snapshots = result.daily_snapshots
        days = list(range(1, len(snapshots) + 1))
        income = [s.coins_earned_today for s in snapshots]
        spending = [s.coins_spent_today for s in snapshots]
        balance = [s.coins_balance for s in snapshots]
        fig.add_trace(
            go.Scatter(
                x=days,
                y=income,
                fill="tozeroy",
                name="Coin Income",
                line=dict(color="green"),
                fillcolor="rgba(0, 255, 0, 0.3)",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=days,
                y=spending,
                fill="tozeroy",
                name="Coin Spending",
                line=dict(color="red"),
                fillcolor="rgba(255, 0, 0, 0.3)",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=days,
                y=balance,
                mode="lines",
                name="Coin Balance",
                line=dict(color="blue", width=2),
            )
        )
    else:
        means = result.daily_coin_balance_means
        days = list(range(1, len(means) + 1))
        fig.add_trace(
            go.Scatter(
                x=days,
                y=means,
                mode="lines",
                name="Mean Coin Balance",
                line=dict(color="blue", width=2),
            )
        )
        add_coin_balance_ci(fig, result)
    fig.update_layout(
        title="Coin Economy — Income vs Spending",
        xaxis=dict(title="Day"),
        yaxis=dict(title="Coins"),
        hovermode="x unified",
        template="plotly_white",
    )
    st.plotly_chart(fig, width="stretch")
