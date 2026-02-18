"""
Configuration editor page for the Bluestar Economy Simulator.

Provides editable tables organized into 4 tabs:
- Pack Configuration: Pack averages and card type tables
- Upgrade Tables: Duplicate costs, coin costs, and bluestar rewards per category
- Card Economy: Duplicate ranges and coin per duplicate settings
- Progression & Schedule: Progression mapping and unique unlock schedule
"""

import pandas as pd
import streamlit as st

from simulation.config_loader import load_defaults
from simulation.models import CardCategory, SimConfig


def render_config_editor(config: SimConfig) -> None:
    st.title("⚙️ Configuration Editor")
    st.markdown(
        "Edit simulation parameters using validated tables. Changes update immediately."
    )

    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "📦 Pack Configuration",
            "⬆️ Upgrade Tables",
            "💰 Card Economy",
            "📈 Progression & Schedule",
        ]
    )

    with tab1:
        _render_pack_config(config)

    with tab2:
        _render_upgrade_tables(config)

    with tab3:
        _render_card_economy(config)

    with tab4:
        _render_progression_schedule(config)


def _render_pack_config(config: SimConfig) -> None:
    st.subheader("Pack Averages")
    st.caption("20-day average pack opening rates for each pack type")

    pack_avg_df = pd.DataFrame(
        [
            {"Pack Name": pack_name, "20-Day Average": avg}
            for pack_name, avg in config.pack_averages.items()
        ]
    )

    edited_avg = st.data_editor(
        pack_avg_df,
        column_config={
            "Pack Name": st.column_config.TextColumn("Pack Name"),
            "20-Day Average": st.column_config.NumberColumn(
                "20-Day Average",
                min_value=0.0,
                max_value=50.0,
                step=0.1,
                format="%.1f",
                required=True,
            ),
        },
        hide_index=True,
        width="stretch",
        key="pack_averages_editor",
    )

    config.pack_averages = {row._1: row._2 for row in edited_avg.itertuples()}

    st.divider()
    st.subheader("Card Types Tables by Pack")
    st.caption("Mapping of total unlocked cards to types yielded for each pack")

    pack_tabs = st.tabs([pack.name for pack in config.packs])

    for pack, pack_tab in zip(config.packs, pack_tabs):
        with pack_tab:
            card_types_df = pd.DataFrame(
                [
                    {"Total Unlocked": int(k), "Types Yielded": v}
                    for k, v in sorted(
                        pack.card_types_table.items(), key=lambda x: int(x[0])
                    )
                ]
            )

            edited_types = st.data_editor(
                card_types_df,
                column_config={
                    "Total Unlocked": st.column_config.NumberColumn(
                        "Total Unlocked",
                        min_value=0,
                        step=1,
                        format="%d",
                        required=True,
                    ),
                    "Types Yielded": st.column_config.NumberColumn(
                        "Types Yielded", min_value=0, step=1, format="%d", required=True
                    ),
                },
                hide_index=True,
                width="stretch",
                num_rows="dynamic",
                key=f"card_types_{pack.name}",
            )

            pack.card_types_table = {
                str(row._1): row._2 for row in edited_types.itertuples()
            }

    if st.button("🔄 Restore Pack Defaults", key="restore_pack"):
        defaults = load_defaults()
        config.pack_averages = defaults.pack_averages
        for i, pack in enumerate(config.packs):
            pack.card_types_table = defaults.packs[i].card_types_table
        st.rerun()


def _render_upgrade_tables(config: SimConfig) -> None:
    st.subheader("Upgrade Cost & Reward Tables")
    st.caption("Configure upgrade requirements and rewards by card category")

    category = st.selectbox(
        "Select Category:",
        [CardCategory.GOLD_SHARED, CardCategory.BLUE_SHARED, CardCategory.UNIQUE],
        format_func=lambda x: x.value.replace("_", " ").title(),
        key="upgrade_category_select",
    )

    upgrade_table = config.upgrade_tables[category]

    num_levels = len(upgrade_table.duplicate_costs)
    df = pd.DataFrame(
        {
            "Level": range(1, num_levels + 1),
            "Duplicates Required": upgrade_table.duplicate_costs,
            "Coin Cost": upgrade_table.coin_costs,
            "Bluestar Reward": upgrade_table.bluestar_rewards[:num_levels],
        }
    )

    edited_upgrades = st.data_editor(
        df,
        column_config={
            "Level": st.column_config.NumberColumn("Level", disabled=True, format="%d"),
            "Duplicates Required": st.column_config.NumberColumn(
                "Duplicates Required", min_value=0, step=1, format="%d", required=True
            ),
            "Coin Cost": st.column_config.NumberColumn(
                "Coin Cost", min_value=0, step=1, format="%d", required=True
            ),
            "Bluestar Reward": st.column_config.NumberColumn(
                "Bluestar Reward", min_value=0, step=1, format="%d", required=True
            ),
        },
        hide_index=True,
        width="stretch",
        height=400,
        key=f"upgrade_table_{category.value}",
    )

    upgrade_table.duplicate_costs = edited_upgrades["Duplicates Required"].tolist()
    upgrade_table.coin_costs = edited_upgrades["Coin Cost"].tolist()
    upgrade_table.bluestar_rewards[:num_levels] = edited_upgrades[
        "Bluestar Reward"
    ].tolist()

    if st.button(
        f"🔄 Restore {category.value.replace('_', ' ').title()} Defaults",
        key=f"restore_upgrade_{category.value}",
    ):
        defaults = load_defaults()
        config.upgrade_tables[category] = defaults.upgrade_tables[category]
        st.rerun()


def _render_card_economy(config: SimConfig) -> None:
    st.subheader("Duplicate Ranges")
    st.caption("Percentile ranges for duplicate calculations by level and category")

    dup_category = st.selectbox(
        "Select Category for Duplicate Ranges:",
        [CardCategory.GOLD_SHARED, CardCategory.BLUE_SHARED, CardCategory.UNIQUE],
        format_func=lambda x: x.value.replace("_", " ").title(),
        key="dup_range_category_select",
    )

    dup_range = config.duplicate_ranges[dup_category]
    num_levels = len(dup_range.min_pct)

    dup_df = pd.DataFrame(
        {
            "Level": range(1, num_levels + 1),
            "Min Pct": dup_range.min_pct,
            "Max Pct": dup_range.max_pct,
        }
    )

    edited_dup = st.data_editor(
        dup_df,
        column_config={
            "Level": st.column_config.NumberColumn("Level", disabled=True, format="%d"),
            "Min Pct": st.column_config.NumberColumn(
                "Min Pct",
                min_value=0.0,
                max_value=1.0,
                step=0.001,
                format="%.3f",
                required=True,
            ),
            "Max Pct": st.column_config.NumberColumn(
                "Max Pct",
                min_value=0.0,
                max_value=1.0,
                step=0.001,
                format="%.3f",
                required=True,
            ),
        },
        hide_index=True,
        width="stretch",
        height=300,
        key=f"dup_range_{dup_category.value}",
    )

    dup_range.min_pct = edited_dup["Min Pct"].tolist()
    dup_range.max_pct = edited_dup["Max Pct"].tolist()

    st.divider()
    st.subheader("Coin Per Duplicate")
    st.caption("Coin rewards for duplicates by level and category")

    coin_category = st.selectbox(
        "Select Category for Coin Rewards:",
        [CardCategory.GOLD_SHARED, CardCategory.BLUE_SHARED, CardCategory.UNIQUE],
        format_func=lambda x: x.value.replace("_", " ").title(),
        key="coin_per_dup_category_select",
    )

    coin_per_dup = config.coin_per_duplicate[coin_category]
    num_coin_levels = len(coin_per_dup.coins_per_dupe)

    coin_df = pd.DataFrame(
        {"Level": range(1, num_coin_levels + 1), "Coins": coin_per_dup.coins_per_dupe}
    )

    edited_coin = st.data_editor(
        coin_df,
        column_config={
            "Level": st.column_config.NumberColumn("Level", disabled=True, format="%d"),
            "Coins": st.column_config.NumberColumn(
                "Coins", min_value=0, step=1, format="%d", required=True
            ),
        },
        hide_index=True,
        width="stretch",
        height=300,
        key=f"coin_per_dup_{coin_category.value}",
    )

    coin_per_dup.coins_per_dupe = edited_coin["Coins"].tolist()

    if st.button("🔄 Restore Economy Defaults", key="restore_economy"):
        defaults = load_defaults()
        config.duplicate_ranges = defaults.duplicate_ranges
        config.coin_per_duplicate = defaults.coin_per_duplicate
        st.rerun()


def _render_progression_schedule(config: SimConfig) -> None:
    st.subheader("Progression Mapping")
    st.caption("Maps shared card levels to corresponding unique card levels")

    prog_df = pd.DataFrame(
        {
            "Shared Level": config.progression_mapping.shared_levels,
            "Unique Level": config.progression_mapping.unique_levels,
        }
    )

    edited_prog = st.data_editor(
        prog_df,
        column_config={
            "Shared Level": st.column_config.NumberColumn(
                "Shared Level", min_value=1, step=1, format="%d", required=True
            ),
            "Unique Level": st.column_config.NumberColumn(
                "Unique Level", min_value=1, step=1, format="%d", required=True
            ),
        },
        hide_index=True,
        width="stretch",
        key="progression_mapping_editor",
    )

    config.progression_mapping.shared_levels = edited_prog["Shared Level"].tolist()
    config.progression_mapping.unique_levels = edited_prog["Unique Level"].tolist()

    st.divider()
    st.subheader("Unique Unlock Schedule")
    st.caption("Number of unique cards unlocked on specific days")

    schedule_df = pd.DataFrame(
        [
            {"Day": int(day), "Count": count}
            for day, count in sorted(
                config.unique_unlock_schedule.items(), key=lambda x: int(x[0])
            )
        ]
    )

    edited_schedule = st.data_editor(
        schedule_df,
        column_config={
            "Day": st.column_config.NumberColumn(
                "Day", min_value=0, step=1, format="%d", required=True
            ),
            "Count": st.column_config.NumberColumn(
                "Count", min_value=0, step=1, format="%d", required=True
            ),
        },
        hide_index=True,
        width="stretch",
        num_rows="dynamic",
        key="unique_unlock_schedule_editor",
    )

    config.unique_unlock_schedule = {
        row.Day: row.Count for row in edited_schedule.itertuples()
    }

    if st.button("🔄 Restore Defaults", key="restore_progression"):
        defaults = load_defaults()
        config.progression_mapping = defaults.progression_mapping
        config.unique_unlock_schedule = defaults.unique_unlock_schedule
        st.rerun()
