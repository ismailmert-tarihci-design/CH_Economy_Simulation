import json

import pandas as pd
import streamlit as st

from simulation.config_loader import (
    load_defaults,
    list_profiles,
    load_profile,
    save_profile,
    delete_profile,
)
from simulation.models import (
    CardCategory,
    CardTypesRange,
    GearDesignIncomeRow,
    GearSlotCostConfig,
    GearSlotCostRow,
    HeroUnlockRow,
    PetBuildConfig,
    PetBuildRow,
    PetDuplicateConfig,
    PetDuplicateRow,
    PetLevelConfig,
    PetLevelRow,
    PetTierConfig,
    PetTierRow,
    SimConfig,
    UserProfile,
)


def render_pack_config(config: SimConfig) -> None:
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
        use_container_width=True,
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
                use_container_width=True,
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


def render_upgrade_tables(config: SimConfig) -> None:
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
        use_container_width=True,
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


def render_card_economy(config: SimConfig) -> None:
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
        use_container_width=True,
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
        use_container_width=True,
        height=300,
        key=f"coin_per_dup_{coin_category.value}",
    )

    coin_per_dup.coins_per_dupe = edited_coin["Coins"].tolist()

    if st.button("🔄 Restore Economy Defaults", key="restore_economy"):
        defaults = load_defaults()
        config.duplicate_ranges = defaults.duplicate_ranges
        config.coin_per_duplicate = defaults.coin_per_duplicate
        st.rerun()


def render_progression_schedule(config: SimConfig) -> None:
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
        use_container_width=True,
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
        use_container_width=True,
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


def render_drop_algorithm(config: SimConfig) -> None:
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
            help="Shared pull ratio when progression is balanced (gap=0). Excel formula: rawRatio starts here.",
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
            help="Unique pull ratio when balanced. Should equal 1 - Base Shared Rate.",
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
    st.caption(
        "The exponential gap formula nudges drop rates to follow the progression mapping. "
        "Gap = Sunique - Sshared. WShared = BaseShared × gap_base^Gap, WUnique = BaseUnique × gap_base^(-Gap)."
    )
    col_gap, col_pool = st.columns(2)
    with col_gap:
        config.gap_base = st.number_input(
            "Gap Base (Exponential)",
            min_value=1.0,
            max_value=5.0,
            value=float(config.gap_base),
            step=0.1,
            format="%.1f",
            key="gap_base",
            help="Exponential base for gap adjustment. Higher values make the algorithm "
            "react more aggressively to progression imbalance. Revamp Master Doc: 1.5",
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


def render_profiles(config: SimConfig) -> None:
    st.subheader("User Profiles")
    st.caption("Save and load full simulation configurations.")

    profiles = list_profiles()
    if profiles:
        selected = st.selectbox("Select Profile", profiles, key="profile_select")
        col_load, col_del = st.columns(2)
        with col_load:
            if st.button("📂 Load Profile", key="load_profile"):
                profile = load_profile(selected)
                if profile.full_config is not None:
                    loaded = SimConfig.model_validate(profile.full_config)
                    for field in loaded.model_fields:
                        setattr(config, field, getattr(loaded, field))
                else:
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
            config_dict = json.loads(config.model_dump_json())
            profile = UserProfile(
                name=new_name.strip(),
                daily_pack_schedule=config.daily_pack_schedule,
                unique_unlock_schedule=config.unique_unlock_schedule,
                full_config=config_dict,
            )
            save_profile(profile)
            st.success(f"Saved profile '{new_name.strip()}'")
            st.rerun()
        else:
            st.warning("Enter a profile name.")


def render_pet_hero_gear(config: SimConfig) -> None:
    st.caption(
        "Use section editors for quick updates and bulk tools for high-volume changes. "
        "Bulk apply actions only run when you press Apply."
    )

    st.subheader("Pet System")
    if config.pet_system_config is None:
        st.warning("Pet system config is missing.")
    else:
        pet_config = config.pet_system_config
        eggs_rows = pet_config.eggs_per_day or [
            {"day_start": 1, "day_end": 365, "eggs": 2}
        ]
        eggs_df = pd.DataFrame(eggs_rows)
        edited_eggs = st.data_editor(
            eggs_df,
            column_config={
                "day_start": st.column_config.NumberColumn(
                    "Day Start", min_value=1, step=1, format="%d", required=True
                ),
                "day_end": st.column_config.NumberColumn(
                    "Day End", min_value=1, step=1, format="%d", required=True
                ),
                "eggs": st.column_config.NumberColumn(
                    "Eggs / Day", min_value=0, step=1, format="%d", required=True
                ),
            },
            hide_index=True,
            use_container_width=True,
            num_rows="dynamic",
            key="pet_eggs_per_day",
        )
        pet_config.eggs_per_day = [
            {
                "day_start": int(row.day_start),
                "day_end": int(row.day_end),
                "eggs": int(row.eggs),
            }
            for row in edited_eggs.itertuples()
        ]
        col_a, col_b, col_c, col_d = st.columns(4)
        col_a.metric(
            "Tier Rows",
            len(pet_config.tier_table.tiers if pet_config.tier_table else []),
        )
        col_b.metric(
            "Level Rows",
            len(pet_config.level_table.levels if pet_config.level_table else []),
        )
        col_c.metric(
            "Duplicate Rows",
            len(
                pet_config.duplicate_table.duplicates
                if pet_config.duplicate_table
                else []
            ),
        )
        col_d.metric(
            "Build Rows",
            len(pet_config.build_table.builds if pet_config.build_table else []),
        )

        with st.expander("Pet Tier Table", expanded=False):
            if pet_config.tier_table is None:
                st.warning("Pet tier table is missing.")
            else:
                rarity_keys = sorted(
                    {
                        rarity
                        for row in pet_config.tier_table.tiers
                        for rarity in row.rarity_probabilities.keys()
                    }
                )
                tier_df = pd.DataFrame(
                    [
                        {
                            "tier": row.tier,
                            "summons_to_lvl_up": row.summons_to_lvl_up,
                            **{
                                rarity: float(row.rarity_probabilities.get(rarity, 0.0))
                                for rarity in rarity_keys
                            },
                        }
                        for row in pet_config.tier_table.tiers
                    ]
                )
                edited_tier = st.data_editor(
                    tier_df,
                    column_config={
                        "tier": st.column_config.NumberColumn(
                            "Tier", min_value=1, max_value=15, step=1, disabled=True
                        ),
                        "summons_to_lvl_up": st.column_config.NumberColumn(
                            "Summons To Lvl Up",
                            min_value=0,
                            step=1,
                            format="%d",
                            required=True,
                        ),
                        **{
                            rarity: st.column_config.NumberColumn(
                                rarity,
                                min_value=0.0,
                                max_value=100.0,
                                step=0.1,
                                format="%.1f",
                                required=True,
                            )
                            for rarity in rarity_keys
                        },
                    },
                    hide_index=True,
                    use_container_width=True,
                    key="pet_tier_editor",
                )
                if st.button("Apply Pet Tier Changes", key="apply_pet_tier"):
                    pet_config.tier_table = PetTierConfig(
                        tiers=[
                            PetTierRow(
                                tier=int(row.tier),
                                summons_to_lvl_up=int(row.summons_to_lvl_up),
                                rarity_probabilities={
                                    rarity: float(getattr(row, rarity))
                                    for rarity in rarity_keys
                                },
                            )
                            for row in edited_tier.itertuples()
                        ]
                    )
                    st.success("Pet tier table updated.")

        with st.expander("Pet Level Cost Table", expanded=False):
            if pet_config.level_table is None:
                st.warning("Pet level table is missing.")
            else:
                rarity_filter = st.selectbox(
                    "Rarity",
                    sorted({row.rarity for row in pet_config.level_table.levels}),
                    key="pet_level_rarity_filter",
                )
                level_df = pd.DataFrame(
                    [
                        {
                            "rarity": row.rarity,
                            "level": row.level,
                            "resource_required": row.resource_required,
                        }
                        for row in pet_config.level_table.levels
                        if row.rarity == rarity_filter
                    ]
                )
                edited_levels = st.data_editor(
                    level_df,
                    column_config={
                        "rarity": st.column_config.TextColumn("Rarity", disabled=True),
                        "level": st.column_config.NumberColumn("Level", disabled=True),
                        "resource_required": st.column_config.NumberColumn(
                            "Resource Required",
                            min_value=0,
                            step=1,
                            format="%d",
                            required=True,
                        ),
                    },
                    hide_index=True,
                    use_container_width=True,
                    key=f"pet_level_editor_{rarity_filter}",
                )
                if st.button(
                    "Apply Pet Level Changes", key=f"apply_pet_level_{rarity_filter}"
                ):
                    new_rows = []
                    edited_by_level = {
                        int(row.level): int(row.resource_required)
                        for row in edited_levels.itertuples()
                    }
                    for row in pet_config.level_table.levels:
                        if row.rarity == rarity_filter and row.level in edited_by_level:
                            new_rows.append(
                                PetLevelRow(
                                    rarity=row.rarity,
                                    level=row.level,
                                    resource_required=edited_by_level[row.level],
                                )
                            )
                        else:
                            new_rows.append(row)
                    pet_config.level_table = PetLevelConfig(levels=new_rows)
                    st.success(f"Pet level costs updated for rarity '{rarity_filter}'.")

        with st.expander("Pet Duplicate Requirement Table", expanded=False):
            if pet_config.duplicate_table is None:
                st.warning("Pet duplicate table is missing.")
            else:
                rarity_filter = st.selectbox(
                    "Rarity",
                    sorted(
                        {row.rarity for row in pet_config.duplicate_table.duplicates}
                    ),
                    key="pet_duplicate_rarity_filter",
                )
                duplicate_df = pd.DataFrame(
                    [
                        {
                            "rarity": row.rarity,
                            "level": row.level,
                            "duplicates_required": row.duplicates_required,
                        }
                        for row in pet_config.duplicate_table.duplicates
                        if row.rarity == rarity_filter
                    ]
                )
                edited_duplicates = st.data_editor(
                    duplicate_df,
                    column_config={
                        "rarity": st.column_config.TextColumn("Rarity", disabled=True),
                        "level": st.column_config.NumberColumn("Level", disabled=True),
                        "duplicates_required": st.column_config.NumberColumn(
                            "Duplicates Required",
                            min_value=0,
                            step=1,
                            format="%d",
                            required=True,
                        ),
                    },
                    hide_index=True,
                    use_container_width=True,
                    key=f"pet_duplicate_editor_{rarity_filter}",
                )
                if st.button(
                    "Apply Pet Duplicate Changes",
                    key=f"apply_pet_duplicate_{rarity_filter}",
                ):
                    new_rows = []
                    edited_by_level = {
                        int(row.level): int(row.duplicates_required)
                        for row in edited_duplicates.itertuples()
                    }
                    for row in pet_config.duplicate_table.duplicates:
                        if row.rarity == rarity_filter and row.level in edited_by_level:
                            new_rows.append(
                                PetDuplicateRow(
                                    rarity=row.rarity,
                                    level=row.level,
                                    duplicates_required=edited_by_level[row.level],
                                )
                            )
                        else:
                            new_rows.append(row)
                    pet_config.duplicate_table = PetDuplicateConfig(duplicates=new_rows)
                    st.success(
                        f"Pet duplicate requirements updated for rarity '{rarity_filter}'."
                    )

        with st.expander("Pet Build Cost Table", expanded=False):
            if pet_config.build_table is None:
                st.warning("Pet build table is missing.")
            else:
                build_df = pd.DataFrame(
                    [
                        {
                            "build_level": row.build_level,
                            "spirit_stones_cost": row.spirit_stones_cost,
                        }
                        for row in pet_config.build_table.builds
                    ]
                )
                edited_build = st.data_editor(
                    build_df,
                    column_config={
                        "build_level": st.column_config.NumberColumn(
                            "Build Level",
                            min_value=1,
                            max_value=8,
                            step=1,
                            disabled=True,
                        ),
                        "spirit_stones_cost": st.column_config.NumberColumn(
                            "Spirit Stones Cost",
                            min_value=0,
                            step=1,
                            format="%d",
                            required=True,
                        ),
                    },
                    hide_index=True,
                    use_container_width=True,
                    key="pet_build_editor",
                )
                if st.button("Apply Pet Build Changes", key="apply_pet_build"):
                    pet_config.build_table = PetBuildConfig(
                        builds=[
                            PetBuildRow(
                                build_level=int(row.build_level),
                                spirit_stones_cost=int(row.spirit_stones_cost),
                            )
                            for row in edited_build.itertuples()
                        ]
                    )
                    st.success("Pet build costs updated.")

    st.divider()
    st.subheader("Hero System")
    if config.hero_system_config is None:
        st.warning("Hero system config is missing.")
    else:
        hero_config = config.hero_system_config
        hero_rows = hero_config.unlock_rows or []
        hero_df = pd.DataFrame(
            [
                {
                    "day": row.day,
                    "hero_id": row.hero_id,
                    "unique_cards_added": row.unique_cards_added,
                }
                for row in hero_rows
            ]
        )
        edited_hero = st.data_editor(
            hero_df,
            column_config={
                "day": st.column_config.NumberColumn(
                    "Day", min_value=1, step=1, format="%d", required=True
                ),
                "hero_id": st.column_config.TextColumn("Hero ID", required=True),
                "unique_cards_added": st.column_config.NumberColumn(
                    "Unique Cards Added",
                    min_value=0,
                    step=1,
                    format="%d",
                    required=True,
                ),
            },
            hide_index=True,
            use_container_width=True,
            num_rows="dynamic",
            key="hero_unlock_rows",
        )
        hero_config.unlock_rows = [
            HeroUnlockRow(
                day=int(row.day),
                hero_id=str(row.hero_id),
                unique_cards_added=int(row.unique_cards_added),
            )
            for row in edited_hero.itertuples()
        ]

        with st.expander("Hero Bulk Paste (CSV)", expanded=False):
            bulk_text = st.text_area(
                "Paste rows as day,hero_id,unique_cards_added",
                value="",
                key="hero_bulk_paste",
                height=120,
            )
            if st.button("Apply Hero Bulk Paste", key="apply_hero_bulk"):
                rows = []
                for line in bulk_text.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    day, hero_id, unique_cards_added = [
                        part.strip() for part in line.split(",", 2)
                    ]
                    rows.append(
                        HeroUnlockRow(
                            day=int(day),
                            hero_id=hero_id,
                            unique_cards_added=int(unique_cards_added),
                        )
                    )
                hero_config.unlock_rows = rows
                st.success(f"Applied {len(rows)} hero unlock rows.")

    st.divider()
    st.subheader("Gear System")
    if config.gear_system_config is None:
        st.warning("Gear system config is missing.")
    else:
        gear_config = config.gear_system_config
        if gear_config.design_income is None:
            st.warning("Gear design income table is missing.")
        else:
            income_df = pd.DataFrame(
                [
                    {
                        "day_start": row.day_start,
                        "day_end": row.day_end,
                        "designs_per_day": row.designs_per_day,
                    }
                    for row in gear_config.design_income.income_table
                ]
            )
            edited_income = st.data_editor(
                income_df,
                column_config={
                    "day_start": st.column_config.NumberColumn(
                        "Day Start", min_value=1, step=1, format="%d", required=True
                    ),
                    "day_end": st.column_config.NumberColumn(
                        "Day End", min_value=1, step=1, format="%d", required=True
                    ),
                    "designs_per_day": st.column_config.NumberColumn(
                        "Designs / Day", min_value=0, step=1, format="%d", required=True
                    ),
                },
                hide_index=True,
                use_container_width=True,
                num_rows="dynamic",
                key="gear_income_rows",
            )
            gear_config.design_income.income_table = [
                GearDesignIncomeRow(
                    day_start=int(row.day_start),
                    day_end=int(row.day_end),
                    designs_per_day=int(row.designs_per_day),
                )
                for row in edited_income.itertuples()
            ]
        slot_cost_rows = (
            gear_config.slot_costs.cost_table
            if gear_config.slot_costs is not None
            else []
        )
        st.caption(
            f"Slot cost rows loaded: {len(slot_cost_rows)} (slots 1..6, levels 1..100)"
        )

        with st.expander("Gear Slot Cost Table", expanded=False):
            if gear_config.slot_costs is None:
                st.warning("Gear slot cost table is missing.")
            else:
                selected_slot = st.selectbox(
                    "Slot",
                    [1, 2, 3, 4, 5, 6],
                    key="gear_slot_cost_filter",
                )
                slot_df = pd.DataFrame(
                    [
                        {
                            "slot_id": row.slot_id,
                            "level": row.level,
                            "design_cost": row.design_cost,
                        }
                        for row in gear_config.slot_costs.cost_table
                        if row.slot_id == selected_slot
                    ]
                )
                level_window = st.slider(
                    "Level Window",
                    min_value=1,
                    max_value=100,
                    value=(1, 25),
                    key=f"gear_level_window_{selected_slot}",
                )
                filtered_slot_df = slot_df[
                    (slot_df["level"] >= level_window[0])
                    & (slot_df["level"] <= level_window[1])
                ].copy()
                edited_slot = st.data_editor(
                    filtered_slot_df,
                    column_config={
                        "slot_id": st.column_config.NumberColumn("Slot", disabled=True),
                        "level": st.column_config.NumberColumn("Level", disabled=True),
                        "design_cost": st.column_config.NumberColumn(
                            "Design Cost",
                            min_value=0,
                            step=1,
                            format="%d",
                            required=True,
                        ),
                    },
                    hide_index=True,
                    use_container_width=True,
                    key=f"gear_slot_editor_{selected_slot}_{level_window[0]}_{level_window[1]}",
                )
                if st.button(
                    "Apply Gear Slot Window Changes",
                    key=f"apply_gear_slot_{selected_slot}_{level_window[0]}_{level_window[1]}",
                ):
                    cost_map = {
                        (row.slot_id, row.level): row.design_cost
                        for row in gear_config.slot_costs.cost_table
                    }
                    for row in edited_slot.itertuples():
                        cost_map[(int(row.slot_id), int(row.level))] = int(
                            row.design_cost
                        )
                    rebuilt_rows = [
                        GearSlotCostRow(
                            slot_id=slot_id,
                            level=level,
                            design_cost=cost_map[(slot_id, level)],
                        )
                        for slot_id in range(1, 7)
                        for level in range(1, 101)
                    ]
                    gear_config.slot_costs = GearSlotCostConfig(cost_table=rebuilt_rows)
                    st.success("Gear slot costs updated for selected window.")

                st.caption("Quick generator for full 6x100 slot cost table")
                col_base, col_step, col_slot = st.columns(3)
                base_cost = col_base.number_input(
                    "Base Cost", min_value=0, value=1, step=1, key="gear_gen_base"
                )
                level_step = col_step.number_input(
                    "Level Step",
                    min_value=0,
                    value=1,
                    step=1,
                    key="gear_gen_level_step",
                )
                slot_step = col_slot.number_input(
                    "Slot Step", min_value=0, value=0, step=1, key="gear_gen_slot_step"
                )
                if st.button(
                    "Regenerate Full Gear Cost Table", key="regen_gear_cost_table"
                ):
                    rows = []
                    for slot_id in range(1, 7):
                        for level in range(1, 101):
                            cost = int(
                                base_cost
                                + (level - 1) * level_step
                                + (slot_id - 1) * slot_step
                            )
                            rows.append(
                                GearSlotCostRow(
                                    slot_id=slot_id,
                                    level=level,
                                    design_cost=max(0, cost),
                                )
                            )
                    gear_config.slot_costs = GearSlotCostConfig(cost_table=rows)
                    st.success(
                        "Regenerated complete gear slot cost table (6 slots x 100 levels)."
                    )
