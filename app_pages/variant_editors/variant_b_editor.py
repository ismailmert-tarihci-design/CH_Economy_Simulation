"""Variant B config editor — Hero Card System.

Every parameter is editable from the frontend: heroes, card pools, skill trees,
XP tables, upgrade costs, premium packs, drop algorithm settings, joker rates.
"""

import json

import pandas as pd
import streamlit as st

from simulation.variants.variant_b.models import (
    HeroCardConfig,
    HeroCardDef,
    HeroCardRarity,
    HeroDef,
    HeroUpgradeCostTable,
    PremiumPackCardRate,
    PremiumPackDef,
    PremiumPackRarity,
    PremiumPackSchedule,
    SkillTreeNode,
)


def render_variant_b_editor(config: HeroCardConfig) -> None:
    st.markdown("Edit Hero Card System parameters. All changes update immediately.")

    # Top-level settings
    col1, col2, col3 = st.columns(3)
    with col1:
        config.initial_coins = st.number_input("Initial Coins", min_value=0, value=config.initial_coins, step=100, key="vb_coins")
    with col2:
        config.initial_bluestars = st.number_input("Initial Bluestars", min_value=0, value=config.initial_bluestars, step=10, key="vb_stars")
    with col3:
        config.num_days = st.number_input("Simulation Days", min_value=1, max_value=730, value=config.num_days, step=1, key="vb_days")

    col4, col5 = st.columns(2)
    with col4:
        config.num_gold_cards = st.number_input("Gold Shared Cards", min_value=1, max_value=50, value=config.num_gold_cards, key="vb_gold")
    with col5:
        config.num_blue_cards = st.number_input("Blue Shared Cards", min_value=1, max_value=50, value=config.num_blue_cards, key="vb_blue")

    tabs = st.tabs([
        "Heroes & Cards",
        "Skill Trees",
        "XP & Leveling",
        "Upgrade Costs",
        "Drop Algorithm",
        "Hero Joker",
        "Premium Packs",
        "Pack Schedule",
        "Import / Export",
    ])

    with tabs[0]:
        _render_heroes_tab(config)
    with tabs[1]:
        _render_skill_tree_tab(config)
    with tabs[2]:
        _render_xp_tab(config)
    with tabs[3]:
        _render_upgrade_costs_tab(config)
    with tabs[4]:
        _render_drop_algorithm_tab(config)
    with tabs[5]:
        _render_joker_tab(config)
    with tabs[6]:
        _render_premium_packs_tab(config)
    with tabs[7]:
        _render_pack_schedule_tab(config)
    with tabs[8]:
        _render_import_export(config)


def _render_heroes_tab(config: HeroCardConfig) -> None:
    st.subheader("Heroes & Card Pools")

    if not config.heroes:
        st.info("No heroes configured. Add one below.")

    hero_names = [h.name for h in config.heroes]
    if hero_names:
        selected_idx = st.selectbox("Select Hero", range(len(hero_names)), format_func=lambda i: hero_names[i], key="vb_hero_select")
        hero = config.heroes[selected_idx]

        col1, col2, col3 = st.columns(3)
        with col1:
            hero.hero_id = st.text_input("Hero ID", value=hero.hero_id, key=f"vb_hid_{selected_idx}")
        with col2:
            hero.name = st.text_input("Hero Name", value=hero.name, key=f"vb_hname_{selected_idx}")
        with col3:
            hero.max_level = st.number_input("Max Level", min_value=1, max_value=100, value=hero.max_level, key=f"vb_hmax_{selected_idx}")

        # Card pool table
        st.markdown(f"**Card Pool** ({len(hero.card_pool)} cards)")
        if hero.card_pool:
            card_df = pd.DataFrame([
                {
                    "Card ID": c.card_id,
                    "Name": c.name,
                    "Rarity": c.rarity.value,
                    "XP on Upgrade": c.base_xp_on_upgrade,
                    "Starter": c.card_id in hero.starter_card_ids,
                }
                for c in hero.card_pool
            ])
            edited = st.data_editor(
                card_df,
                column_config={
                    "Rarity": st.column_config.SelectboxColumn(
                        "Rarity", options=[r.value for r in HeroCardRarity], required=True
                    ),
                    "XP on Upgrade": st.column_config.NumberColumn("XP on Upgrade", min_value=0, step=1),
                    "Starter": st.column_config.CheckboxColumn("Starter"),
                },
                use_container_width=True,
                hide_index=True,
                num_rows="dynamic",
                key=f"vb_cards_{selected_idx}",
            )

            # Apply edits back
            new_cards = []
            new_starters = []
            for _, row in edited.iterrows():
                new_cards.append(HeroCardDef(
                    card_id=str(row["Card ID"]),
                    hero_id=hero.hero_id,
                    rarity=HeroCardRarity(row["Rarity"]),
                    name=str(row["Name"]),
                    base_xp_on_upgrade=int(row["XP on Upgrade"]),
                ))
                if row.get("Starter", False):
                    new_starters.append(str(row["Card ID"]))
            hero.card_pool = new_cards
            hero.starter_card_ids = new_starters

    # Unlock schedule
    st.divider()
    st.subheader("Hero Unlock Schedule")
    st.caption("Day -> Heroes unlocked (comma-separated hero IDs)")
    schedule_rows = [
        {"Day": int(d), "Hero IDs": ", ".join(hids)}
        for d, hids in sorted(config.hero_unlock_schedule.items(), key=lambda x: int(x[0]))
    ]
    if not schedule_rows:
        schedule_rows = [{"Day": 0, "Hero IDs": ""}]
    sched_df = pd.DataFrame(schedule_rows)
    edited_sched = st.data_editor(sched_df, use_container_width=True, hide_index=True, num_rows="dynamic", key="vb_unlock_sched")
    config.hero_unlock_schedule = {}
    for _, row in edited_sched.iterrows():
        day = int(row["Day"])
        ids = [s.strip() for s in str(row["Hero IDs"]).split(",") if s.strip()]
        if ids:
            config.hero_unlock_schedule[day] = ids


def _render_skill_tree_tab(config: HeroCardConfig) -> None:
    st.subheader("Skill Trees (Linear)")
    if not config.heroes:
        st.info("Add heroes first.")
        return

    hero_names = [h.name for h in config.heroes]
    idx = st.selectbox("Select Hero", range(len(hero_names)), format_func=lambda i: hero_names[i], key="vb_tree_hero")
    hero = config.heroes[idx]

    if hero.skill_tree:
        tree_df = pd.DataFrame([
            {
                "Node": n.node_index,
                "Level Required": n.hero_level_required,
                "Cards Unlocked": ", ".join(n.cards_unlocked),
                "Perk Label": n.perk_label,
            }
            for n in hero.skill_tree
        ])
        edited = st.data_editor(tree_df, use_container_width=True, hide_index=True, num_rows="dynamic", key=f"vb_tree_{idx}")
        hero.skill_tree = []
        for _, row in edited.iterrows():
            cards = [s.strip() for s in str(row["Cards Unlocked"]).split(",") if s.strip()]
            hero.skill_tree.append(SkillTreeNode(
                node_index=int(row["Node"]),
                hero_level_required=int(row["Level Required"]),
                cards_unlocked=cards,
                perk_label=str(row.get("Perk Label", "")),
            ))
    else:
        st.info("No skill tree nodes configured for this hero.")


def _render_xp_tab(config: HeroCardConfig) -> None:
    st.subheader("Hero XP Thresholds")
    if not config.heroes:
        st.info("Add heroes first.")
        return

    hero_names = [h.name for h in config.heroes]
    idx = st.selectbox("Select Hero", range(len(hero_names)), format_func=lambda i: hero_names[i], key="vb_xp_hero")
    hero = config.heroes[idx]

    xp_df = pd.DataFrame({
        "Level": range(1, len(hero.xp_per_level) + 1),
        "XP Required": hero.xp_per_level,
    })
    edited = st.data_editor(
        xp_df,
        column_config={
            "Level": st.column_config.NumberColumn("Level", disabled=True),
            "XP Required": st.column_config.NumberColumn("XP Required", min_value=1, step=10),
        },
        use_container_width=True,
        hide_index=True,
        key=f"vb_xp_{idx}",
    )
    hero.xp_per_level = edited["XP Required"].tolist()


def _render_upgrade_costs_tab(config: HeroCardConfig) -> None:
    st.subheader("Hero Card Upgrade Costs (per Rarity)")

    if not config.hero_upgrade_tables:
        st.info("No upgrade tables configured.")
        return

    rarity_names = [t.rarity.value for t in config.hero_upgrade_tables]
    sel = st.selectbox("Rarity", range(len(rarity_names)), format_func=lambda i: rarity_names[i], key="vb_upcost_rarity")
    table = config.hero_upgrade_tables[sel]

    num_levels = len(table.duplicate_costs)
    df = pd.DataFrame({
        "Level": range(1, num_levels + 1),
        "Duplicate Cost": table.duplicate_costs,
        "Coin Cost": table.coin_costs,
        "Bluestar Reward": table.bluestar_rewards[:num_levels],
        "XP Reward": table.xp_rewards[:num_levels],
    })
    edited = st.data_editor(
        df,
        column_config={
            "Level": st.column_config.NumberColumn("Level", disabled=True),
            "Duplicate Cost": st.column_config.NumberColumn(min_value=0, step=1),
            "Coin Cost": st.column_config.NumberColumn(min_value=0, step=10),
            "Bluestar Reward": st.column_config.NumberColumn(min_value=0, step=1),
            "XP Reward": st.column_config.NumberColumn(min_value=0, step=1),
        },
        use_container_width=True,
        hide_index=True,
        key=f"vb_upgcost_{sel}",
    )
    table.duplicate_costs = edited["Duplicate Cost"].tolist()
    table.coin_costs = edited["Coin Cost"].tolist()
    table.bluestar_rewards = edited["Bluestar Reward"].tolist()
    table.xp_rewards = edited["XP Reward"].tolist()


def _render_drop_algorithm_tab(config: HeroCardConfig) -> None:
    st.subheader("Drop Algorithm Settings")
    dc = config.drop_config

    col1, col2 = st.columns(2)
    with col1:
        dc.hero_vs_shared_base_rate = st.slider(
            "Hero vs Shared Base Rate",
            min_value=0.0, max_value=1.0, value=dc.hero_vs_shared_base_rate, step=0.05,
            help="Probability of pulling a hero card vs shared card",
            key="vb_hero_rate",
        )
    with col2:
        dc.card_selection_mode = st.selectbox(
            "Card Selection Mode",
            ["lowest_level", "weighted_rarity", "equal"],
            index=["lowest_level", "weighted_rarity", "equal"].index(dc.card_selection_mode)
            if dc.card_selection_mode in ["lowest_level", "weighted_rarity", "equal"] else 0,
            key="vb_card_mode",
        )

    col3, col4 = st.columns(2)
    with col3:
        dc.pity_counter_threshold = st.number_input(
            "Pity Counter (0=disabled)",
            min_value=0, max_value=100, value=dc.pity_counter_threshold, step=1,
            help="Guarantee hero card after N shared-only pulls",
            key="vb_pity",
        )
    with col4:
        dc.streak_decay_shared = st.number_input(
            "Streak Decay (Shared)", min_value=0.0, max_value=1.0,
            value=dc.streak_decay_shared, step=0.05, key="vb_sd_shared",
        )

    dc.streak_decay_hero = st.number_input(
        "Streak Decay (Hero)", min_value=0.0, max_value=1.0,
        value=dc.streak_decay_hero, step=0.05, key="vb_sd_hero",
    )


def _render_joker_tab(config: HeroCardConfig) -> None:
    st.subheader("Hero Joker Settings")
    config.joker_drop_rate_in_regular_packs = st.slider(
        "Joker Drop Rate in Regular Packs",
        min_value=0.0, max_value=0.20, value=config.joker_drop_rate_in_regular_packs,
        step=0.005, format="%.3f",
        help="Chance of a hero joker dropping per regular pack pull",
        key="vb_joker_rate",
    )
    st.info("Hero jokers can also drop from premium packs (configured per pack).")


def _render_premium_packs_tab(config: HeroCardConfig) -> None:
    st.subheader("Premium Card Packs")

    if not config.premium_packs:
        st.info("No premium packs configured.")
        return

    pack_names = [f"{p.name} ({p.pack_rarity.value})" for p in config.premium_packs]
    sel = st.selectbox("Select Pack", range(len(pack_names)), format_func=lambda i: pack_names[i], key="vb_ppack_sel")
    pack = config.premium_packs[sel]

    col1, col2, col3 = st.columns(3)
    with col1:
        pack.name = st.text_input("Pack Name", value=pack.name, key=f"vb_pp_name_{sel}")
    with col2:
        pack.diamond_cost = st.number_input("Diamond Cost", min_value=0, value=pack.diamond_cost, step=50, key=f"vb_pp_cost_{sel}")
    with col3:
        pack.cards_per_pack = st.number_input("Cards per Pack", min_value=1, max_value=50, value=pack.cards_per_pack, step=1, key=f"vb_pp_cpp_{sel}")

    col4, col5 = st.columns(2)
    with col4:
        pack.joker_rate = st.slider("Joker Rate", min_value=0.0, max_value=0.30, value=pack.joker_rate, step=0.01, key=f"vb_pp_jr_{sel}")
    with col5:
        pack.dupe_boost_multiplier = st.number_input("Dupe Boost Multiplier", min_value=0.5, max_value=5.0, value=pack.dupe_boost_multiplier, step=0.1, key=f"vb_pp_db_{sel}")

    st.markdown("**Per-Card Drop Rates**")
    if pack.card_drop_rates:
        rates_df = pd.DataFrame([
            {"Card ID": r.card_id, "Drop Rate": r.drop_rate}
            for r in pack.card_drop_rates
        ])
        edited = st.data_editor(
            rates_df,
            column_config={
                "Drop Rate": st.column_config.NumberColumn("Drop Rate", min_value=0.0, step=0.1, format="%.2f"),
            },
            use_container_width=True,
            hide_index=True,
            key=f"vb_pp_rates_{sel}",
        )
        pack.card_drop_rates = [
            PremiumPackCardRate(card_id=str(row["Card ID"]), drop_rate=float(row["Drop Rate"]))
            for _, row in edited.iterrows()
        ]


def _render_pack_schedule_tab(config: HeroCardConfig) -> None:
    st.subheader("Daily Pack Schedule (Regular)")
    if config.daily_pack_schedule:
        sched_df = pd.DataFrame(config.daily_pack_schedule)
        sched_df.insert(0, "Day", range(1, len(sched_df) + 1))
        edited = st.data_editor(sched_df, use_container_width=True, hide_index=True, key="vb_daily_packs")
        config.daily_pack_schedule = [
            {col: float(row[col]) for col in edited.columns if col != "Day"}
            for _, row in edited.iterrows()
        ]

    st.divider()
    st.subheader("Premium Pack Availability Schedule")
    if config.premium_pack_schedule:
        avail_df = pd.DataFrame([
            {"Pack ID": s.pack_id, "From Day": s.available_from_day, "Until Day": s.available_until_day}
            for s in config.premium_pack_schedule
        ])
        edited = st.data_editor(avail_df, use_container_width=True, hide_index=True, num_rows="dynamic", key="vb_pp_sched")
        config.premium_pack_schedule = [
            PremiumPackSchedule(
                pack_id=str(row["Pack ID"]),
                available_from_day=int(row["From Day"]),
                available_until_day=int(row["Until Day"]),
            )
            for _, row in edited.iterrows()
        ]

    st.divider()
    st.subheader("Simulated Premium Purchases")
    st.caption("How many premium packs the simulated player buys per day cycle.")
    if config.premium_pack_purchase_schedule:
        purch_df = pd.DataFrame(config.premium_pack_purchase_schedule)
        purch_df.insert(0, "Day", range(1, len(purch_df) + 1))
        edited = st.data_editor(purch_df, use_container_width=True, hide_index=True, num_rows="dynamic", key="vb_pp_purchases")
        config.premium_pack_purchase_schedule = [
            {col: int(row[col]) for col in edited.columns if col != "Day"}
            for _, row in edited.iterrows()
        ]


def _render_import_export(config: HeroCardConfig) -> None:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Export")
        st.download_button(
            "Download Config JSON",
            data=config.model_dump_json(indent=2),
            file_name="hero_card_config.json",
            mime="application/json",
            use_container_width=True,
        )
    with col2:
        st.subheader("Import")
        uploaded = st.file_uploader("Upload config JSON", type=["json"], key="vb_import")
        if uploaded:
            try:
                content = uploaded.read().decode("utf-8")
                imported = HeroCardConfig.model_validate_json(content)
                st.session_state.configs["variant_b"] = imported
                st.success("Config imported. Reloading...")
                st.rerun()
            except Exception as e:
                st.error(f"Invalid config: {e}")
