"""Additional dashboard charts for stakeholder transparency."""

from typing import Any

import plotly.graph_objects as go
import streamlit as st


def render_kpi_row(result: Any, mode: str) -> None:
    if mode == "deterministic":
        total_upgrades = (
            sum(result.total_upgrades.values()) if result.total_upgrades else 0
        )
        cols = st.columns(4)
        cols[0].metric("Total Bluestars", f"{result.total_bluestars:,}")
        cols[1].metric("Coins Earned", f"{result.total_coins_earned:,}")
        cols[2].metric("Coins Spent", f"{result.total_coins_spent:,}")
        cols[3].metric("Total Upgrades", f"{total_upgrades:,}")
    else:
        mean, std = result.bluestar_stats.result()
        cols = st.columns(3)
        cols[0].metric("Mean Final Bluestars", f"{mean:,.0f} ± {std:,.0f}")
        cols[1].metric("MC Runs", f"{result.num_runs}")
        cols[2].metric("Completion Time", f"{result.completion_time:.1f}s")


def render_upgrades_chart(result: Any) -> None:
    snapshots = result.daily_snapshots
    days = list(range(1, len(snapshots) + 1))
    upgrade_counts = [len(s.upgrades_today) for s in snapshots]
    bluestars_daily = [s.bluestars_earned_today for s in snapshots]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=days,
            y=upgrade_counts,
            name="Upgrades",
            marker_color="rgb(148, 103, 189)",
            opacity=0.7,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=days,
            y=bluestars_daily,
            mode="lines",
            name="Bluestars Earned",
            line=dict(color="rgb(31, 119, 180)", width=2),
            yaxis="y2",
        )
    )
    fig.update_layout(
        title="Daily Upgrades & Bluestar Earnings",
        xaxis=dict(title="Day"),
        yaxis=dict(title="Upgrade Count", side="left"),
        yaxis2=dict(title="Bluestars Earned", side="right", overlaying="y"),
        hovermode="x unified",
        template="plotly_white",
        legend=dict(x=0.01, y=0.99),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_unique_unlocked_chart(result: Any) -> None:
    snapshots = result.daily_snapshots
    days = list(range(1, len(snapshots) + 1))
    unlocked = [s.total_unique_unlocked for s in snapshots]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=days,
            y=unlocked,
            mode="lines",
            name="Unique Cards Unlocked",
            line=dict(color="rgb(255, 127, 14)", width=2),
            line_shape="hv",
        )
    )
    fig.update_layout(
        title="Unique Cards Unlocked Over Time",
        xaxis=dict(title="Day"),
        yaxis=dict(title="Cards Unlocked", dtick=1),
        hovermode="x unified",
        template="plotly_white",
    )
    st.plotly_chart(fig, use_container_width=True)


def add_category_ci(fig: go.Figure, result: Any) -> None:
    COLORS = {
        "GOLD_SHARED": "rgba(255, 215, 0, 0.15)",
        "BLUE_SHARED": "rgba(65, 105, 225, 0.15)",
        "UNIQUE": "rgba(255, 69, 0, 0.15)",
    }
    stds_by_cat = result.daily_category_level_stds
    means_by_cat = result.daily_category_level_means

    for category in ["GOLD_SHARED", "BLUE_SHARED", "UNIQUE"]:
        if category not in means_by_cat or category not in stds_by_cat:
            continue
        means = means_by_cat[category]
        stds = stds_by_cat[category]
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
                fillcolor=COLORS[category],
                line=dict(color="rgba(255,255,255,0)"),
                name=f"{category.replace('_', ' ').title()} 95% CI",
                showlegend=False,
                hoverinfo="skip",
            )
        )


def add_coin_balance_ci(fig: go.Figure, result: Any) -> None:
    means = result.daily_coin_balance_means
    stds = result.daily_coin_balance_stds
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
            fillcolor="rgba(0, 0, 255, 0.15)",
            line=dict(color="rgba(255,255,255,0)"),
            name="95% CI",
            showlegend=True,
            hoverinfo="skip",
        )
    )


PULL_TYPE_COLORS = {
    "GOLD_SHARED": "#FFD700",
    "BLUE_SHARED": "#4169E1",
    "UNIQUE": "#FF4500",
}

PULL_TYPE_DISPLAY = {
    "GOLD_SHARED": "Gold Shared",
    "BLUE_SHARED": "Blue Shared",
    "UNIQUE": "Unique",
}


def render_pull_counts_chart(result: Any, mode: str) -> None:
    fig = go.Figure()
    if mode == "deterministic":
        snapshots = result.daily_snapshots
        days = list(range(1, len(snapshots) + 1))
        for card_type in ["GOLD_SHARED", "BLUE_SHARED", "UNIQUE"]:
            counts = [s.pull_counts_by_type.get(card_type, 0) for s in snapshots]
            fig.add_trace(
                go.Bar(
                    x=days,
                    y=counts,
                    name=PULL_TYPE_DISPLAY.get(card_type, card_type),
                    marker_color=PULL_TYPE_COLORS.get(card_type, "gray"),
                )
            )
        fig.update_layout(barmode="stack")
    else:
        means_by_type = result.daily_pull_count_means
        num_days = len(next(iter(means_by_type.values()))) if means_by_type else 0
        days = list(range(1, num_days + 1))
        for card_type in ["GOLD_SHARED", "BLUE_SHARED", "UNIQUE"]:
            if card_type in means_by_type:
                fig.add_trace(
                    go.Scatter(
                        x=days,
                        y=means_by_type[card_type],
                        mode="lines",
                        name=PULL_TYPE_DISPLAY.get(card_type, card_type),
                        line=dict(
                            color=PULL_TYPE_COLORS.get(card_type, "gray"), width=2
                        ),
                        stackgroup="one",
                    )
                )
    fig.update_layout(
        title="Daily Pull Counts by Card Type",
        xaxis=dict(title="Day"),
        yaxis=dict(title="Pull Count"),
        hovermode="x unified",
        template="plotly_white",
    )
    st.plotly_chart(fig, use_container_width=True)


def render_pack_counts_chart(result: Any, mode: str) -> None:
    fig = go.Figure()
    if mode == "deterministic":
        snapshots = result.daily_snapshots
        days = list(range(1, len(snapshots) + 1))
        pack_names = set()
        for s in snapshots:
            pack_names.update(s.pack_counts_by_type.keys())
        for pack_name in sorted(pack_names):
            counts = [s.pack_counts_by_type.get(pack_name, 0) for s in snapshots]
            fig.add_trace(go.Bar(x=days, y=counts, name=pack_name))
        fig.update_layout(barmode="stack")
    else:
        means_by_pack = result.daily_pack_count_means
        if means_by_pack:
            num_days = len(next(iter(means_by_pack.values())))
            days = list(range(1, num_days + 1))
            for pack_name in sorted(means_by_pack.keys()):
                fig.add_trace(
                    go.Scatter(
                        x=days,
                        y=means_by_pack[pack_name],
                        mode="lines",
                        name=pack_name,
                        line=dict(width=2),
                        stackgroup="one",
                    )
                )
    fig.update_layout(
        title="Daily Card Pulls by Pack Type",
        xaxis=dict(title="Day"),
        yaxis=dict(title="Card Pulls from Pack"),
        hovermode="x unified",
        template="plotly_white",
    )
    st.plotly_chart(fig, use_container_width=True)
