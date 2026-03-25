"""Dashboard with interactive Plotly charts for simulation results."""

from typing import Any

import plotly.graph_objects as go
import streamlit as st
import pandas as pd

from app_pages.dashboard_charts import (
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

    col_save, col_spacer = st.columns([1, 4])
    with col_save:
        if st.button("💾 Save This Result", use_container_width=True):
            st.session_state.show_save_dialog = True

    if st.session_state.get("show_save_dialog", False):
        with st.container(border=True):
            st.markdown("**Save Simulation Result**")
            save_name = st.text_input(
                "Name",
                value=f"Sim_{mode}_{result.total_bluestars if mode == 'deterministic' else 'MC'}",
            )
            save_desc = st.text_area("Description (optional)", height=68)
            col_confirm, col_cancel = st.columns(2)
            with col_confirm:
                if st.button("✅ Save", use_container_width=True):
                    try:
                        from app_pages.results_manager import save_current_result

                        filename = save_current_result(save_name, save_desc)
                        st.session_state.show_save_dialog = False
                        st.success(f"Saved as {filename}!")
                    except Exception as e:
                        st.error(f"Failed to save: {e}")
            with col_cancel:
                if st.button("❌ Cancel", use_container_width=True):
                    st.session_state.show_save_dialog = False
                    st.rerun()

    st.divider()
    _render_bluestar_chart(result, mode)
    _render_card_progression_chart(result, mode)
    if mode == "deterministic":
        _render_upgrades_and_unlocked(result)
    _render_coin_flow_chart(result, mode)
    st.divider()
    render_pull_counts_chart(result, mode)
    render_pack_counts_chart(result, mode)
    if mode == "deterministic":
        _render_pet_hero_gear_events(result)
        _render_pet_hero_gear_details(result)


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
    st.plotly_chart(fig, use_container_width=True)


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
    st.plotly_chart(fig, use_container_width=True)


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
    st.plotly_chart(fig, use_container_width=True)


def _render_pet_hero_gear_events(result: Any) -> None:
    snapshots = result.daily_snapshots
    pet_count = sum(len(s.pet_events) for s in snapshots)
    hero_count = sum(len(s.hero_unlock_events) for s in snapshots)
    gear_count = sum(len(s.gear_events) for s in snapshots)

    st.divider()
    st.subheader("Pet / Hero / Gear Events")
    col1, col2, col3 = st.columns(3)
    col1.metric("Pet Events", f"{pet_count:,}")
    col2.metric("Hero Unlock Events", f"{hero_count:,}")
    col3.metric("Gear Events", f"{gear_count:,}")

    rows = []
    for snapshot in snapshots:
        rows.append(
            {
                "Day": snapshot.day,
                "Pet Events": len(snapshot.pet_events),
                "Hero Unlock Events": len(snapshot.hero_unlock_events),
                "Gear Events": len(snapshot.gear_events),
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_pet_hero_gear_details(result: Any) -> None:
    st.divider()
    st.subheader("Detailed System Dashboards")
    pet_tab, hero_tab, gear_tab = st.tabs(["Pet", "Hero", "Gear"])

    with pet_tab:
        _render_pet_detail_dashboard(result)
    with hero_tab:
        _render_hero_detail_dashboard(result)
    with gear_tab:
        _render_gear_detail_dashboard(result)


def _render_pet_detail_dashboard(result: Any) -> None:
    snapshots = result.daily_snapshots
    owned_pet_ids: set[str] = set()
    current_tier = 1
    rows = []

    for snapshot in snapshots:
        summons = 0
        level_upgrades = 0
        build_upgrades = 0
        for event in snapshot.pet_events:
            if "summon_index" in event:
                summons += 1
                current_tier = max(
                    current_tier, int(event.get("tier_after", current_tier))
                )
                if event.get("owned_after", False):
                    pet_id = event.get("pet_id")
                    if pet_id:
                        owned_pet_ids.add(str(pet_id))
            if event.get("event_type") == "level":
                level_upgrades += 1
            if event.get("event_type") == "build":
                build_upgrades += 1

        rows.append(
            {
                "Day": snapshot.day,
                "Summons": summons,
                "Level Upgrades": level_upgrades,
                "Build Upgrades": build_upgrades,
                "Current Tier": current_tier,
                "Owned Pets": len(owned_pet_ids),
            }
        )

    pet_df = pd.DataFrame(rows)
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Summons", f"{int(pet_df['Summons'].sum()):,}")
    col2.metric(
        "Final Tier", int(pet_df["Current Tier"].iloc[-1]) if not pet_df.empty else 1
    )
    col3.metric("Owned Pets", len(owned_pet_ids))

    fig = go.Figure()
    fig.add_trace(go.Bar(x=pet_df["Day"], y=pet_df["Summons"], name="Summons"))
    fig.add_trace(
        go.Bar(
            x=pet_df["Day"],
            y=pet_df["Level Upgrades"],
            name="Level Upgrades",
        )
    )
    fig.add_trace(
        go.Bar(
            x=pet_df["Day"],
            y=pet_df["Build Upgrades"],
            name="Build Upgrades",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=pet_df["Day"],
            y=pet_df["Current Tier"],
            mode="lines+markers",
            name="Tier",
            yaxis="y2",
        )
    )
    fig.update_layout(
        title="Pet Progression by Day",
        xaxis=dict(title="Day"),
        yaxis=dict(title="Counts"),
        yaxis2=dict(title="Tier", overlaying="y", side="right"),
        barmode="group",
        template="plotly_white",
    )
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(pet_df, use_container_width=True, hide_index=True)


def _render_hero_detail_dashboard(result: Any) -> None:
    snapshots = result.daily_snapshots
    unlocked_heroes: set[str] = set()
    current_pool = 0
    rows = []

    for snapshot in snapshots:
        added = 0
        for event in snapshot.hero_unlock_events:
            added += int(event.get("unique_cards_added", 0))
            hero_id = event.get("hero_id")
            if hero_id:
                unlocked_heroes.add(str(hero_id))
            current_pool = max(
                current_pool, int(event.get("total_unique_pool_after", current_pool))
            )
        rows.append(
            {
                "Day": snapshot.day,
                "Unique Cards Added": added,
                "Total Unique Pool": current_pool,
                "Unlocked Heroes": len(unlocked_heroes),
            }
        )

    hero_df = pd.DataFrame(rows)
    col1, col2, col3 = st.columns(3)
    col1.metric(
        "Total Unique Cards Added", f"{int(hero_df['Unique Cards Added'].sum()):,}"
    )
    col2.metric(
        "Final Unique Pool",
        int(hero_df["Total Unique Pool"].iloc[-1]) if not hero_df.empty else 0,
    )
    col3.metric("Unlocked Heroes", len(unlocked_heroes))

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=hero_df["Day"],
            y=hero_df["Unique Cards Added"],
            name="Unique Cards Added",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=hero_df["Day"],
            y=hero_df["Total Unique Pool"],
            mode="lines+markers",
            name="Total Unique Pool",
        )
    )
    fig.update_layout(
        title="Hero Unlock Progression",
        xaxis=dict(title="Day"),
        yaxis=dict(title="Unique Cards"),
        template="plotly_white",
    )
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(hero_df, use_container_width=True, hide_index=True)


def _render_gear_detail_dashboard(result: Any) -> None:
    snapshots = result.daily_snapshots
    slot_levels = {slot_id: 1 for slot_id in range(1, 7)}
    rows = []

    for snapshot in snapshots:
        daily_upgrades = 0
        for event in snapshot.gear_events:
            slot_id = int(event.get("slot_id", 0))
            if 1 <= slot_id <= 6:
                slot_levels[slot_id] = max(
                    slot_levels[slot_id], int(event.get("new_level", 1))
                )
                daily_upgrades += 1
        rows.append(
            {
                "Day": snapshot.day,
                "Daily Gear Upgrades": daily_upgrades,
                "Average Gear Level": sum(slot_levels.values()) / 6.0,
                **{f"Slot {slot_id}": slot_levels[slot_id] for slot_id in range(1, 7)},
            }
        )

    gear_df = pd.DataFrame(rows)
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Gear Upgrades", f"{int(gear_df['Daily Gear Upgrades'].sum()):,}")
    col2.metric(
        "Final Avg Gear Level",
        f"{float(gear_df['Average Gear Level'].iloc[-1]):.2f}"
        if not gear_df.empty
        else "1.00",
    )
    col3.metric(
        "Highest Slot Level",
        int(max(slot_levels.values())) if slot_levels else 1,
    )

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=gear_df["Day"], y=gear_df["Daily Gear Upgrades"], name="Daily Upgrades"
        )
    )
    fig.add_trace(
        go.Scatter(
            x=gear_df["Day"],
            y=gear_df["Average Gear Level"],
            mode="lines+markers",
            name="Average Gear Level",
            yaxis="y2",
        )
    )
    fig.update_layout(
        title="Gear Progression",
        xaxis=dict(title="Day"),
        yaxis=dict(title="Daily Upgrades"),
        yaxis2=dict(title="Average Level", overlaying="y", side="right"),
        template="plotly_white",
    )
    st.plotly_chart(fig, use_container_width=True)

    slot_fig = go.Figure()
    for slot_id in range(1, 7):
        slot_fig.add_trace(
            go.Scatter(
                x=gear_df["Day"],
                y=gear_df[f"Slot {slot_id}"],
                mode="lines",
                name=f"Slot {slot_id}",
            )
        )
    slot_fig.update_layout(
        title="Per-Slot Gear Levels",
        xaxis=dict(title="Day"),
        yaxis=dict(title="Slot Level"),
        template="plotly_white",
    )
    st.plotly_chart(slot_fig, use_container_width=True)
    st.dataframe(gear_df, use_container_width=True, hide_index=True)
