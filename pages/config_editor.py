import pandas as pd
import streamlit as st

from simulation.config_loader import (
    load_defaults,
    list_profiles,
    load_profile,
    save_profile,
    delete_profile,
)
from simulation.models import CardCategory, CardTypesRange, SimConfig, UserProfile


def render_config_editor(config: SimConfig) -> None:
    st.title("⚙️ Configuration Editor")
    st.markdown("Edit simulation parameters. Changes update immediately.")

    col_coins, col_stars = st.columns(2)
    with col_coins:
        config.initial_coins = st.number_input(
            "Initial Coins",
            min_value=0,
            value=config.initial_coins,
            step=100,
            key="init_coins",
        )
    with col_stars:
        config.initial_bluestars = st.number_input(
            "Initial Bluestars",
            min_value=0,
            value=config.initial_bluestars,
            step=10,
            key="init_stars",
        )

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        [
            "📦 Pack Configuration",
            "⬆️ Upgrade Tables",
            "💰 Card Economy",
            "📈 Progression & Schedule",
            "🎲 Drop Algorithm",
            "👤 Profiles",
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
    with tab5:
        _render_drop_algorithm(config)
    with tab6:
        _render_profiles(config)


def _render_pack_config(config: SimConfig) -> None:
    st.subheader("Daily Pack Schedule")
    st.caption(
        "Pack counts per day. Schedule loops when simulation exceeds its length."
    )

    pack_names = [p.name for p in config.packs]
    current_len = len(config.daily_pack_schedule) if config.daily_pack_schedule else 1

    schedule_len = st.number_input(
        "Schedule Length (days)",
        min_value=1,
        max_value=28,
        value=min(current_len, 28),
        step=1,
        key="sched_len",
    )
    while len(config.daily_pack_schedule) < schedule_len:
        config.daily_pack_schedule.append({name: 0.0 for name in pack_names})
    if len(config.daily_pack_schedule) > schedule_len:
        config.daily_pack_schedule = config.daily_pack_schedule[:schedule_len]

    rows = []
    for i, day_counts in enumerate(config.daily_pack_schedule):
        row = {"Day": i + 1}
        for name in pack_names:
            row[name] = float(day_counts.get(name, 0.0))
        rows.append(row)

    schedule_df = pd.DataFrame(rows)
    edited_sched = st.data_editor(
        schedule_df,
        column_config={
            "Day": st.column_config.NumberColumn("Day", disabled=True, format="%d"),
            **{
                name: st.column_config.NumberColumn(
                    name, min_value=0.0, max_value=50.0, step=0.5, format="%.1f"
                )
                for name in pack_names
            },
        },
        hide_index=True,
        width="stretch",
        height=min(400, 35 + schedule_len * 35),
        key="daily_schedule_editor",
    )
    config.daily_pack_schedule = [
        {name: float(row[name]) for name in pack_names}
        for _, row in edited_sched.iterrows()
    ]

    st.divider()
    st.subheader("Card Types Tables by Pack")
    st.caption("Mapping of total unlocked cards to types yielded for each pack")

    pack_tabs = st.tabs(pack_names)
    for pack, pack_tab in zip(config.packs, pack_tabs):
        with pack_tab:
            card_types_df = pd.DataFrame(
                [
                    {
                        "Unlocked Card Count": int(k),
                        "Min Card Types": int(v.min),
                        "Max Card Types": int(v.max),
                    }
                    for k, v in sorted(
                        pack.card_types_table.items(), key=lambda x: int(x[0])
                    )
                ]
            )
            edited_types = st.data_editor(
                card_types_df,
                column_config={
                    "Unlocked Card Count": st.column_config.NumberColumn(
                        "Unlocked Card Count",
                        min_value=0,
                        step=1,
                        format="%d",
                        required=True,
                    ),
                    "Min Card Types": st.column_config.NumberColumn(
                        "Min Card Types",
                        min_value=0,
                        step=1,
                        format="%d",
                        required=True,
                    ),
                    "Max Card Types": st.column_config.NumberColumn(
                        "Max Card Types",
                        min_value=0,
                        step=1,
                        format="%d",
                        required=True,
                    ),
                },
                hide_index=True,
                width="stretch",
                num_rows="dynamic",
                key=f"card_types_{pack.name}",
            )
            pack.card_types_table = {
                int(row._1): CardTypesRange(min=int(row._2), max=int(row._3))
                for row in edited_types.itertuples()
            }

    if st.button("🔄 Restore Pack Defaults", key="restore_pack"):
        defaults = load_defaults()
        config.daily_pack_schedule = defaults.daily_pack_schedule
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


def _render_drop_algorithm(config: SimConfig) -> None:
    st.subheader("Drop Algorithm Parameters")
    st.caption("Controls the card drop rarity decision and selection weights.")

    st.markdown("**Base Drop Rates**")
    col_shared, col_unique = st.columns(2)
    with col_shared:
        config.base_shared_rate = st.number_input(
            "Base Shared Rate",
            min_value=0.0,
            max_value=1.0,
            value=float(config.base_shared_rate),
            step=0.05,
            format="%.2f",
            key="base_shared_rate",
        )
    with col_unique:
        config.base_unique_rate = st.number_input(
            "Base Unique Rate",
            min_value=0.0,
            max_value=1.0,
            value=float(config.base_unique_rate),
            step=0.05,
            format="%.2f",
            key="base_unique_rate",
        )

    st.divider()
    st.markdown("**Streak Decay Rates**")
    st.caption("Lower values = stronger penalty for consecutive same-type drops.")
    col_sd_shared, col_sd_unique = st.columns(2)
    with col_sd_shared:
        config.streak_decay_shared = st.number_input(
            "Streak Decay (Shared)",
            min_value=0.0,
            max_value=1.0,
            value=float(config.streak_decay_shared),
            step=0.05,
            format="%.2f",
            key="streak_decay_shared",
        )
    with col_sd_unique:
        config.streak_decay_unique = st.number_input(
            "Streak Decay (Unique)",
            min_value=0.0,
            max_value=1.0,
            value=float(config.streak_decay_unique),
            step=0.05,
            format="%.2f",
            key="streak_decay_unique",
        )

    st.divider()
    st.markdown("**Gap Balancing & Candidate Pool**")
    col_gap, col_pool = st.columns(2)
    with col_gap:
        config.gap_base = st.number_input(
            "Gap Base",
            min_value=1.0,
            max_value=5.0,
            value=float(config.gap_base),
            step=0.1,
            format="%.1f",
            key="gap_base",
            help="Exponential base for progression gap balancing. Higher = stronger catch-up.",
        )
    with col_pool:
        config.unique_candidate_pool = st.number_input(
            "Unique Candidate Pool",
            min_value=1,
            max_value=50,
            value=int(config.unique_candidate_pool),
            step=1,
            key="unique_candidate_pool",
            help="Top-N lowest-level unique cards considered for selection.",
        )

    if st.button("🔄 Restore Drop Algorithm Defaults", key="restore_drop_algo"):
        config.base_shared_rate = 0.70
        config.base_unique_rate = 0.30
        config.streak_decay_shared = 0.6
        config.streak_decay_unique = 0.3
        config.gap_base = 1.5
        config.unique_candidate_pool = 10
        st.rerun()


def _render_profiles(config: SimConfig) -> None:
    st.subheader("User Profiles")
    st.caption("Save and load pack schedule + unlock schedule presets.")

    profiles = list_profiles()
    if profiles:
        selected = st.selectbox("Select Profile", profiles, key="profile_select")
        col_load, col_del = st.columns(2)
        with col_load:
            if st.button("📂 Load Profile", key="load_profile"):
                profile = load_profile(selected)
                config.daily_pack_schedule = profile.daily_pack_schedule
                config.unique_unlock_schedule = profile.unique_unlock_schedule
                st.rerun()
        with col_del:
            if st.button("🗑️ Delete Profile", key="del_profile"):
                delete_profile(selected)
                st.rerun()
    else:
        st.info("No saved profiles yet.")

    st.divider()
    new_name = st.text_input("Profile Name", key="new_profile_name")
    if st.button("💾 Save Profile", key="save_profile"):
        if new_name.strip():
            profile = UserProfile(
                name=new_name.strip(),
                daily_pack_schedule=config.daily_pack_schedule,
                unique_unlock_schedule=config.unique_unlock_schedule,
            )
            save_profile(profile)
            st.success(f"Saved profile '{new_name.strip()}'")
            st.rerun()
        else:
            st.warning("Enter a profile name.")
