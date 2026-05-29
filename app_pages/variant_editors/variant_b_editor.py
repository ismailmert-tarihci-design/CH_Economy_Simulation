"""Variant B config editor — Hero Card System.

Every parameter is editable from the frontend: heroes, card pools, skill trees,
XP tables, upgrade costs, premium packs, drop algorithm settings.
"""

import json

import pandas as pd
import streamlit as st

from app_pages.bulk_edit_helpers import render_bulk_edit_bar
from simulation.models import UserProfile
from simulation.variants.variant_b.config_loader import (
    list_vb_profiles, load_vb_profile, save_vb_profile, delete_vb_profile,
)
from simulation.variants.variant_b.models import (
    HeroCardConfig,
    HeroCardDef,
    HeroCardRarity,
    HeroCardTypesRange,
    HeroPackType,
    PremiumPackPullRarity,
    SkillTreeNode,
)


def render_variant_b_editor(config: HeroCardConfig) -> None:
    st.caption("Hero card system parameters. All changes update immediately.")

    with st.container(border=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            config.initial_coins = st.number_input("Initial coins", min_value=0, value=config.initial_coins, step=100, key="vb_coins")
        with col2:
            config.initial_bluestars = st.number_input("Initial bluestars", min_value=0, value=config.initial_bluestars, step=10, key="vb_stars")
        with col3:
            config.num_days = st.number_input("Simulation days", min_value=1, max_value=730, value=config.num_days, step=1, key="vb_days")

        col4, col5, col6 = st.columns(3)
        with col4:
            config.num_gold_cards = st.number_input("Gold shared cards", min_value=1, max_value=50, value=config.num_gold_cards, key="vb_gold")
        with col5:
            config.num_blue_cards = st.number_input("Blue shared cards", min_value=1, max_value=50, value=config.num_blue_cards, key="vb_blue")
        with col6:
            config.num_gray_cards = st.number_input("Gray shared cards", min_value=1, max_value=50, value=config.num_gray_cards, key="vb_gray")

    tabs = st.tabs([
        ":material/person: Heroes & cards",
        ":material/schedule: Hero unlock timeline",
        ":material/account_tree: Skill trees",
        ":material/trending_up: Shared XP",
        ":material/paid: Hero upgrade costs",
        ":material/layers: Shared upgrades",
        ":material/percent: Hero dupe ranges",
        ":material/percent: Shared dupe ranges",
        ":material/casino: Drop algorithm",
        ":material/inventory_2: Hero packs",
        ":material/redeem: Pack bonuses",
        ":material/calendar_today: Pack schedule",
        ":material/person: Profiles",
        ":material/swap_horiz: Import / export",
    ])

    with tabs[0]:
        _render_heroes_tab(config)
    with tabs[1]:
        _render_unlock_timeline_tab(config)
    with tabs[2]:
        _render_skill_tree_tab(config)
    with tabs[3]:
        _render_xp_tab(config)
    with tabs[4]:
        _render_upgrade_costs_tab(config)
    with tabs[5]:
        _render_shared_upgrade_tab(config)
    with tabs[6]:
        _render_duplicate_ranges_tab(config)
    with tabs[7]:
        _render_shared_dupe_ranges_tab(config)
    with tabs[8]:
        _render_drop_algorithm_tab(config)
    with tabs[9]:
        _render_premium_packs_tab(config)
    with tabs[10]:
        _render_pack_bonuses_tab(config)
    with tabs[11]:
        _render_pack_schedule_tab(config)
    with tabs[12]:
        _render_profiles_tab(config)
    with tabs[13]:
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
        st.caption(
            "XP rewards per upgrade are defined per-level in the **Hero upgrade costs** tab "
            "(one value per card level, per rarity)."
        )
        if hero.card_pool:
            # Preserve each card's existing base_xp_on_upgrade so it survives the round-trip;
            # it's not shown here because XP is per-level, not per-card.
            existing_xp = {c.card_id: c.base_xp_on_upgrade for c in hero.card_pool}

            card_df = pd.DataFrame([
                {
                    "Card ID": c.card_id,
                    "Name": c.name,
                    "Rarity": c.rarity.value,
                    "Starter": c.card_id in hero.starter_card_ids,
                }
                for c in hero.card_pool
            ])

            bulk = render_bulk_edit_bar(f"hero_cards_{selected_idx}", card_df, label=f"{hero.name} Card Pool")
            if bulk is not None:
                card_df = bulk

            edited = st.data_editor(
                card_df,
                column_config={
                    "Rarity": st.column_config.SelectboxColumn(
                        "Rarity", options=[r.value for r in HeroCardRarity], required=True
                    ),
                    "Starter": st.column_config.CheckboxColumn("Starter"),
                },
                width="stretch",
                hide_index=True,
                num_rows="dynamic",
                key=f"vb_cards_{selected_idx}",
            )

            # Apply edits back
            new_cards = []
            new_starters = []
            for _, row in edited.iterrows():
                card_id = str(row["Card ID"])
                new_cards.append(HeroCardDef(
                    card_id=card_id,
                    hero_id=hero.hero_id,
                    rarity=HeroCardRarity(row["Rarity"]),
                    name=str(row["Name"]),
                    base_xp_on_upgrade=existing_xp.get(card_id, 0),
                ))
                if row.get("Starter", False):
                    new_starters.append(card_id)
            hero.card_pool = new_cards
            hero.starter_card_ids = new_starters

    st.divider()
    st.caption("Use the **Hero unlock timeline** tab to edit when each hero becomes available.")


def _render_unlock_timeline_tab(config: HeroCardConfig) -> None:
    st.subheader("Hero Unlock Timeline")
    st.caption(
        "Set the **total-bluestar threshold** at which each hero unlocks. "
        "Heroes come online with progression (bluestars earned), not on a "
        "calendar day."
    )

    if not config.heroes:
        st.info("Add heroes first in the Heroes & Cards tab.")
        return

    # Build a flat list: one row per hero with their unlock bluestar threshold.
    # Invert schedule: hero_id -> bluestar threshold
    hero_bs_map: dict[str, int] = {}
    for threshold, hids in config.hero_unlock_schedule.items():
        for hid in hids:
            hero_bs_map[hid] = int(threshold)

    rows = []
    for hero in config.heroes:
        rows.append({
            "Hero": hero.name,
            "hero_id": hero.hero_id,
            "Unlock Bluestars": hero_bs_map.get(hero.hero_id, 0),
        })
    rows.sort(key=lambda r: r["Unlock Bluestars"])

    timeline_df = pd.DataFrame(rows)

    # Visual timeline chart
    import plotly.express as px  # type: ignore[import-untyped]

    max_bs = max((r["Unlock Bluestars"] for r in rows), default=0)
    fig = px.scatter(
        timeline_df, x="Unlock Bluestars", y="Hero",
        color="Hero",
        title="Hero Unlock Timeline (by total bluestars)",
        labels={"Unlock Bluestars": "Total bluestars", "Hero": ""},
    )
    fig.update_traces(marker=dict(size=14, symbol="diamond"))
    fig.update_layout(
        xaxis=dict(range=[-50, max_bs + 100]),
        yaxis=dict(autorange="reversed"),
        showlegend=False,
        height=max(350, len(rows) * 28 + 80),
        margin=dict(l=0, r=0, t=40, b=0),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Editable table
    st.markdown("**Edit unlock thresholds below** (total bluestars; one hero per row):")

    edit_df = timeline_df[["Hero", "hero_id", "Unlock Bluestars"]].copy()
    edited = st.data_editor(
        edit_df,
        column_config={
            "Hero": st.column_config.TextColumn("Hero", disabled=True),
            "hero_id": st.column_config.TextColumn("ID", disabled=True),
            "Unlock Bluestars": st.column_config.NumberColumn(
                "Unlock Bluestars",
                min_value=0,
                max_value=10_000_000,
                step=1,
                help="Total bluestars at which this hero unlocks (0 = start)",
            ),
        },
        width="stretch",
        hide_index=True,
        key="vb_unlock_timeline",
    )

    # Write back to config
    new_schedule: dict[int, list[str]] = {}
    for _, row in edited.iterrows():
        threshold = int(row["Unlock Bluestars"])
        hid = str(row["hero_id"])
        new_schedule.setdefault(threshold, []).append(hid)
    config.hero_unlock_schedule = new_schedule


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
                "Token Cost": n.token_cost,
            }
            for n in hero.skill_tree
        ])
        bulk = render_bulk_edit_bar(f"skill_tree_{idx}", tree_df, label=f"{hero.name} Skill Tree")
        if bulk is not None:
            tree_df = bulk
        edited = st.data_editor(tree_df, width="stretch", hide_index=True, num_rows="dynamic", key=f"vb_tree_{idx}")
        hero.skill_tree = []
        for _, row in edited.iterrows():
            cards = [s.strip() for s in str(row["Cards Unlocked"]).split(",") if s.strip()]
            hero.skill_tree.append(SkillTreeNode(
                node_index=int(row["Node"]),
                hero_level_required=int(row["Level Required"]),
                cards_unlocked=cards,
                perk_label=str(row.get("Perk Label", "")),
                token_cost=int(row.get("Token Cost", 0) or 0),
            ))
    else:
        st.info("No skill tree nodes configured for this hero.")


def _render_xp_tab(config: HeroCardConfig) -> None:
    st.subheader("Per-Hero XP Thresholds")
    st.caption("Each hero tracks XP and levels independently. Upgrading a hero's cards grants XP to that hero only.")

    st.info("XP thresholds are configured per hero in the Hero Definitions tab (xp_per_level). "
            "The table below sets the shared default used when creating new heroes.")

    config.shared_max_hero_level = st.number_input(
        "Default max hero level", min_value=1, max_value=200,
        value=config.shared_max_hero_level, step=1, key="vb_shared_max_lvl",
    )

    if not config.shared_xp_per_level:
        config.shared_xp_per_level = [50 + i * 25 for i in range(50)]

    xp_df = pd.DataFrame({
        "Level": range(1, len(config.shared_xp_per_level) + 1),
        "XP Required": config.shared_xp_per_level,
    })
    bulk = render_bulk_edit_bar("shared_xp", xp_df, label="XP Thresholds")
    if bulk is not None:
        xp_df = bulk
    edited = st.data_editor(
        xp_df,
        column_config={
            "Level": st.column_config.NumberColumn("Level", disabled=True),
            "XP Required": st.column_config.NumberColumn("XP Required", min_value=1, step=10),
        },
        width="stretch",
        hide_index=True,
        num_rows="dynamic",
        key="vb_shared_xp",
    )
    config.shared_xp_per_level = edited["XP Required"].tolist()


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
    bulk = render_bulk_edit_bar(f"hero_upgcost_{sel}", df, label=f"{rarity_names[sel]} Upgrade Costs")
    if bulk is not None:
        df = bulk
    edited = st.data_editor(
        df,
        column_config={
            "Level": st.column_config.NumberColumn("Level", disabled=True),
            "Duplicate Cost": st.column_config.NumberColumn(min_value=0, step=1),
            "Coin Cost": st.column_config.NumberColumn(min_value=0, step=10),
            "Bluestar Reward": st.column_config.NumberColumn(min_value=0, step=1),
            "XP Reward": st.column_config.NumberColumn(min_value=0, step=1),
        },
        width="stretch",
        hide_index=True,
        key=f"vb_upgcost_{sel}",
    )
    table.duplicate_costs = edited["Duplicate Cost"].tolist()
    table.coin_costs = edited["Coin Cost"].tolist()
    table.bluestar_rewards = edited["Bluestar Reward"].tolist()
    table.xp_rewards = edited["XP Reward"].tolist()


def _render_shared_upgrade_tab(config: HeroCardConfig) -> None:
    st.subheader("Shared Card Upgrade Costs (per Category)")
    st.caption("Shared card upgrades grant bluestars but no hero XP.")

    if not config.shared_upgrade_tables:
        st.info("No shared upgrade tables configured.")
        return

    cat_names = [t.category for t in config.shared_upgrade_tables]
    sel = st.selectbox("Category", range(len(cat_names)), format_func=lambda i: cat_names[i], key="vb_shared_upcost_cat")
    table = config.shared_upgrade_tables[sel]

    num_levels = len(table.duplicate_costs)
    df = pd.DataFrame({
        "Level": range(1, num_levels + 1),
        "Duplicate Cost": table.duplicate_costs,
        "Coin Cost": table.coin_costs,
        "Bluestar Reward": table.bluestar_rewards[:num_levels],
    })
    bulk = render_bulk_edit_bar(f"shared_upgcost_{sel}", df, label=f"{cat_names[sel]} Shared Upgrade Costs")
    if bulk is not None:
        df = bulk
    edited = st.data_editor(
        df,
        column_config={
            "Level": st.column_config.NumberColumn("Level", disabled=True),
            "Duplicate Cost": st.column_config.NumberColumn(min_value=0, step=1),
            "Coin Cost": st.column_config.NumberColumn(min_value=0, step=10),
            "Bluestar Reward": st.column_config.NumberColumn(min_value=0, step=1),
        },
        width="stretch",
        hide_index=True,
        key=f"vb_shared_upgcost_{sel}",
    )
    table.duplicate_costs = edited["Duplicate Cost"].tolist()
    table.coin_costs = edited["Coin Cost"].tolist()
    table.bluestar_rewards = edited["Bluestar Reward"].tolist()


def _render_drop_algorithm_tab(config: HeroCardConfig) -> None:
    st.subheader("Drop algorithm")
    st.caption("Each step in the flowchart is editable. Changes update the simulation immediately.")
    dc = config.drop_config

    with st.container(border=True):
        st.markdown("**:material/playing_cards: Regular pack pull**")
        st.caption("Player opens a regular pack. Each card pull follows this algorithm.")

    st.markdown("<div style='text-align:center;color:#475569;font-size:28px;font-weight:600'>↓</div>", unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown("**:material/shield: Pity check**")
        dc.pity_counter_threshold = st.number_input(
            "Guarantee hero card after N shared-only pulls (0 = disabled)",
            min_value=0, max_value=100, value=dc.pity_counter_threshold, step=1, key="vb_pity",
        )
        if dc.pity_counter_threshold > 0:
            st.caption(f"After {dc.pity_counter_threshold} shared pulls without a hero card -> force hero card.")
        else:
            st.caption("Pity system disabled.")

    st.markdown("<div style='text-align:center;color:#475569;font-size:28px;font-weight:600'>↓</div>", unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown("**:material/call_split: Hero vs shared**")
        dc.hero_vs_shared_base_rate = st.slider(
            "Hero card probability",
            min_value=0.0, max_value=1.0, value=dc.hero_vs_shared_base_rate, step=0.05, key="vb_hero_rate",
        )
        hero_pct = dc.hero_vs_shared_base_rate * 100
        shared_pct = (1 - dc.hero_vs_shared_base_rate) * 100
        st.markdown(f":blue-badge[Hero {hero_pct:.0f}%] :orange-badge[Shared {shared_pct:.0f}%]")

    col_hero, col_shared = st.columns(2)

    with col_hero:
        st.markdown("<div style='text-align:center;color:#475569;font-size:28px;font-weight:600'>↓ <small>Hero card</small></div>", unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown("**1. Pick bucket**")
            st.caption("Heroes ranked by level, split into 3 tiers")
            dc.bucket_bottom_weight = st.slider("Bottom (lowest level)", min_value=0.0, max_value=1.0, value=dc.bucket_bottom_weight, step=0.05, key="vb_bkt_bot")
            dc.bucket_middle_weight = st.slider("Middle", min_value=0.0, max_value=1.0, value=dc.bucket_middle_weight, step=0.05, key="vb_bkt_mid")
            dc.bucket_top_weight = st.slider("Top (highest level)", min_value=0.0, max_value=1.0, value=dc.bucket_top_weight, step=0.05, key="vb_bkt_top")
            bucket_sum = dc.bucket_bottom_weight + dc.bucket_middle_weight + dc.bucket_top_weight
            if abs(bucket_sum - 1.0) > 0.01:
                st.warning(f"Bucket weights sum to {bucket_sum:.2f} -- should be 1.0")

        st.markdown("<div style='text-align:center;color:#475569;font-size:28px;font-weight:600'>↓</div>", unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown("**2. Pick hero**")
            dc.streak_decay_hero = st.slider("Streak decay multiplier", min_value=0.0, max_value=1.0, value=dc.streak_decay_hero, step=0.05, key="vb_sd_hero")

        st.markdown("<div style='text-align:center;color:#475569;font-size:28px;font-weight:600'>↓</div>", unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown("**3. Roll rarity**")
            dc.rarity_weight_gray = st.slider("Gray", min_value=0.0, max_value=1.0, value=dc.rarity_weight_gray, step=0.01, key="vb_rw_c")
            dc.rarity_weight_blue = st.slider("Blue", min_value=0.0, max_value=1.0, value=dc.rarity_weight_blue, step=0.01, key="vb_rw_r")
            dc.rarity_weight_gold = st.slider("Gold", min_value=0.0, max_value=1.0, value=dc.rarity_weight_gold, step=0.01, key="vb_rw_e")
            rarity_sum = dc.rarity_weight_gray + dc.rarity_weight_blue + dc.rarity_weight_gold
            if abs(rarity_sum - 1.0) > 0.01:
                st.warning(f"Rarity weights sum to {rarity_sum:.2f} -- should be 1.0")

        st.markdown("<div style='text-align:center;color:#475569;font-size:28px;font-weight:600'>↓</div>", unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown("**4. Pick card**")
            st.caption("Lowest-level-first catch-up weighting: weight = 1/(level+1)")

        st.markdown("<div style='text-align:center;color:#475569;font-size:28px;font-weight:600'>↓</div>", unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown("**5. Compute dupes**")
            st.caption("round(dupe_cost x random(min%, max%)) -- see **Dupe Ranges** tab")

    with col_shared:
        st.markdown("<div style='text-align:center;color:#475569;font-size:28px;font-weight:600'>↓ <small>Shared card</small></div>", unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown("**Pick shared card**")
            st.caption(f"Lowest-level-first catch-up across {config.num_gold_cards} Gold + {config.num_blue_cards} Blue + {config.num_gray_cards} Gray cards")

        st.markdown("<div style='text-align:center;color:#475569;font-size:28px;font-weight:600'>↓</div>", unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown("**Compute dupes (per-category)**")
            st.caption("round(dupe_cost x random(min%, max%)) -- see **Shared Dupe Ranges** tab")

        st.markdown("<div style='text-align:center;color:#475569;font-size:28px;font-weight:600'>↓</div>", unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown("**Upgrade (bluestars only)**")
            st.caption("Dupes + Coins -> Level up -> Bluestars. No hero XP. Pity counter +1.")

        with st.container(border=True):
            st.markdown("**Shared streak decay**")
            dc.streak_decay_shared = st.slider("Shared decay multiplier", min_value=0.0, max_value=1.0, value=dc.streak_decay_shared, step=0.05, key="vb_sd_shared")


def _render_premium_packs_tab(config: HeroCardConfig) -> None:
    st.subheader("Hero Unique Packs")
    st.caption(
        "Each hero has one Hero Unique Pack. Per spec: 5 MainUpgradeCards + 1-3 BonusCards, "
        "rarity rolled per PullSinceUniqueGold. After gold, default rarity weights apply. "
        "Pack also rolls jokers, coins, and hero tokens."
    )

    if not config.premium_packs:
        st.info("No hero packs configured.")
        return

    hero_name_map = {h.hero_id: h.name for h in config.heroes}
    pack_labels = [hero_name_map.get(p.featured_hero_ids[0], p.name) if p.featured_hero_ids else p.name for p in config.premium_packs]
    sel = st.selectbox("Select hero", range(len(pack_labels)), format_func=lambda i: pack_labels[i], key="vb_ppack_sel")
    pack = config.premium_packs[sel]

    st.markdown("**Pack-level**")
    c1, c2 = st.columns(2)
    with c1:
        pack.diamond_cost = st.number_input("Diamond Cost", min_value=0, value=pack.diamond_cost, step=50, key=f"vb_pp_cost_{sel}")
    with c2:
        st.caption(f"Pack ID: `{pack.pack_id}`")

    # ── MainUpgradeCards ─────────────────────────────────────────────────────
    st.markdown("**MainUpgradeCards** (100% rate)")
    m1, m2 = st.columns(2)
    with m1:
        pack.main_cards_min = st.number_input("Min #", min_value=0, max_value=20, value=pack.main_cards_min, step=1, key=f"vb_pp_mainmin_{sel}")
    with m2:
        pack.main_cards_max = st.number_input("Max #", min_value=pack.main_cards_min, max_value=20, value=max(pack.main_cards_max, pack.main_cards_min), step=1, key=f"vb_pp_mainmax_{sel}")

    st.caption(
        "Per-rarity dupe % range. Dupes received = round(dupe-cost-for-next-level × random(min%, max%)). "
        "100% means the card jumps exactly one level; 50% means half the dupes needed."
    )
    main_df = pd.DataFrame([
        {
            "Rarity": r,
            "Min %": round(pack.main_dupe_min_pct.get(r, 1.0) * 100, 1),
            "Max %": round(pack.main_dupe_max_pct.get(r, 1.1) * 100, 1),
        }
        for r in ("GRAY", "BLUE", "GOLD")
    ])
    edited_main = st.data_editor(
        main_df,
        column_config={
            "Rarity": st.column_config.TextColumn("Rarity", disabled=True),
            "Min %": st.column_config.NumberColumn("Min %", min_value=0.0, max_value=500.0, step=5.0, format="%.1f"),
            "Max %": st.column_config.NumberColumn("Max %", min_value=0.0, max_value=500.0, step=5.0, format="%.1f"),
        },
        width="stretch", hide_index=True, num_rows="fixed",
        key=f"vb_pp_main_dupes_{sel}",
    )
    pack.main_dupe_min_pct = {str(row["Rarity"]): float(row["Min %"]) / 100.0 for _, row in edited_main.iterrows()}
    pack.main_dupe_max_pct = {str(row["Rarity"]): float(row["Max %"]) / 100.0 for _, row in edited_main.iterrows()}

    _render_dupe_pct_preview(
        config, pack.main_dupe_min_pct, pack.main_dupe_max_pct,
        caption="Sanity check — dupes one MainUpgradeCard pull would yield at the listed card level:",
    )

    # ── BonusCards ───────────────────────────────────────────────────────────
    st.markdown("**BonusCards** (100% rate)")
    b1, b2 = st.columns(2)
    with b1:
        pack.bonus_cards_min = st.number_input("Min #", min_value=0, max_value=20, value=pack.bonus_cards_min, step=1, key=f"vb_pp_bmin_{sel}")
    with b2:
        pack.bonus_cards_max = st.number_input("Max #", min_value=pack.bonus_cards_min, max_value=20, value=max(pack.bonus_cards_max, pack.bonus_cards_min), step=1, key=f"vb_pp_bmax_{sel}")

    st.caption(
        "Per-rarity dupe % range. Same formula as MainUpgradeCards — BonusCards typically use much lower % "
        "(e.g. 20–40%) so a single bonus card alone doesn't level a card up."
    )
    bonus_df = pd.DataFrame([
        {
            "Rarity": r,
            "Min %": round(pack.bonus_dupe_min_pct.get(r, 0.2) * 100, 1),
            "Max %": round(pack.bonus_dupe_max_pct.get(r, 0.4) * 100, 1),
        }
        for r in ("GRAY", "BLUE", "GOLD")
    ])
    edited_bonus = st.data_editor(
        bonus_df,
        column_config={
            "Rarity": st.column_config.TextColumn("Rarity", disabled=True),
            "Min %": st.column_config.NumberColumn("Min %", min_value=0.0, max_value=500.0, step=5.0, format="%.1f"),
            "Max %": st.column_config.NumberColumn("Max %", min_value=0.0, max_value=500.0, step=5.0, format="%.1f"),
        },
        width="stretch", hide_index=True, num_rows="fixed",
        key=f"vb_pp_bonus_dupes_{sel}",
    )
    pack.bonus_dupe_min_pct = {str(row["Rarity"]): float(row["Min %"]) / 100.0 for _, row in edited_bonus.iterrows()}
    pack.bonus_dupe_max_pct = {str(row["Rarity"]): float(row["Max %"]) / 100.0 for _, row in edited_bonus.iterrows()}

    _render_dupe_pct_preview(
        config, pack.bonus_dupe_min_pct, pack.bonus_dupe_max_pct,
        caption="Sanity check — dupes one BonusCard pull would yield at the listed card level:",
    )

    # ── Pack-level extras (jokers, coins, hero tokens) ───────────────────────
    st.markdown("**Pack-level rewards** (rolled once per pack)")
    extras_df = pd.DataFrame([
        {"Reward": "HeroUniqueJoker", "Probability %": round(pack.joker_probability * 100, 1),
         "Min Amount": pack.joker_min, "Max Amount": pack.joker_max},
        {"Reward": "Coins", "Probability %": round(pack.coins_probability * 100, 1),
         "Min Amount": pack.coins_min, "Max Amount": pack.coins_max},
        {"Reward": "HeroTokens", "Probability %": round(pack.hero_tokens_probability * 100, 1),
         "Min Amount": pack.hero_tokens_min, "Max Amount": pack.hero_tokens_max},
    ])
    edited_extras = st.data_editor(
        extras_df,
        column_config={
            "Reward": st.column_config.TextColumn("Reward", disabled=True),
            "Probability %": st.column_config.NumberColumn("Prob %", min_value=0.0, max_value=100.0, step=1.0, format="%.1f"),
            "Min Amount": st.column_config.NumberColumn("Min", min_value=0, step=1),
            "Max Amount": st.column_config.NumberColumn("Max", min_value=0, step=1),
        },
        width="stretch", hide_index=True, num_rows="fixed",
        key=f"vb_pp_extras_{sel}",
    )
    for _, row in edited_extras.iterrows():
        rwd = str(row["Reward"])
        prob = float(row["Probability %"]) / 100.0
        mn = int(row["Min Amount"]) if pd.notna(row["Min Amount"]) else 0
        mx = int(row["Max Amount"]) if pd.notna(row["Max Amount"]) else mn
        if mx < mn:
            mx = mn
        if rwd == "HeroUniqueJoker":
            pack.joker_probability, pack.joker_min, pack.joker_max = prob, mn, mx
        elif rwd == "Coins":
            pack.coins_probability, pack.coins_min, pack.coins_max = prob, mn, mx
        elif rwd == "HeroTokens":
            pack.hero_tokens_probability, pack.hero_tokens_min, pack.hero_tokens_max = prob, mn, mx

    # ── Per-pull rarity schedule (PullSinceUniqueGold) ───────────────────────
    st.markdown("**Rarity per PullSinceUniqueGold**")
    st.caption("Rarity weights indexed by PullSinceUniqueGold (1..N). After a gold is pulled, default rarity weights apply.")

    if pack.pull_rarity_schedule:
        sched_df = pd.DataFrame([
            {"PullSinceUniqueGold": i + 1, "Gray %": round(r.gray_weight * 100, 1),
             "Blue %": round(r.blue_weight * 100, 1), "Gold %": round(r.gold_weight * 100, 1)}
            for i, r in enumerate(pack.pull_rarity_schedule)
        ])
    else:
        sched_df = pd.DataFrame({
            "PullSinceUniqueGold": [1, 2, 3, 4],
            "Gray %": [9.0, 7.0, 5.0, 2.0],
            "Blue %": [40.0, 33.0, 23.0, 12.0],
            "Gold %": [51.0, 60.0, 72.0, 86.0],
        })

    bulk = render_bulk_edit_bar(f"pp_rarity_sched_{sel}", sched_df, label="Pull Rarity Schedule")
    if bulk is not None:
        sched_df = bulk
    edited_sched = st.data_editor(
        sched_df,
        column_config={
            "PullSinceUniqueGold": st.column_config.NumberColumn("PullSinceUniqueGold", disabled=True),
            "Gray %": st.column_config.NumberColumn("Gray %", min_value=0.0, max_value=100.0, step=1.0, format="%.1f"),
            "Blue %": st.column_config.NumberColumn("Blue %", min_value=0.0, max_value=100.0, step=1.0, format="%.1f"),
            "Gold %": st.column_config.NumberColumn("Gold %", min_value=0.0, max_value=100.0, step=1.0, format="%.1f"),
        },
        width="stretch", hide_index=True, num_rows="dynamic",
        key=f"vb_pp_rarity_sched_{sel}",
    )
    pack.pull_rarity_schedule = [
        PremiumPackPullRarity(
            gray_weight=float(row["Gray %"]) / 100.0,
            blue_weight=float(row["Blue %"]) / 100.0,
            gold_weight=float(row["Gold %"]) / 100.0,
        )
        for _, row in edited_sched.iterrows()
    ]

    # Default rarity weights (after gold)
    st.markdown("**Default rarity weights** (after a gold is pulled)")
    dc1, dc2, dc3 = st.columns(3)
    with dc1:
        dg = st.number_input("Gray %", min_value=0.0, max_value=100.0, value=round(pack.default_rarity_weights.gray_weight * 100, 1), step=1.0, format="%.1f", key=f"vb_pp_def_gray_{sel}")
    with dc2:
        db = st.number_input("Blue %", min_value=0.0, max_value=100.0, value=round(pack.default_rarity_weights.blue_weight * 100, 1), step=1.0, format="%.1f", key=f"vb_pp_def_blue_{sel}")
    with dc3:
        dd = st.number_input("Gold %", min_value=0.0, max_value=100.0, value=round(pack.default_rarity_weights.gold_weight * 100, 1), step=1.0, format="%.1f", key=f"vb_pp_def_gold_{sel}")
    pack.default_rarity_weights = PremiumPackPullRarity(gray_weight=dg / 100.0, blue_weight=db / 100.0, gold_weight=dd / 100.0)


def _render_dupe_pct_preview(
    config: HeroCardConfig,
    min_pct_by_rarity: dict[str, float],
    max_pct_by_rarity: dict[str, float],
    caption: str,
) -> None:
    """Show a small preview table converting per-rarity % ranges into actual dupe counts
    at representative card levels. Helps sanity-check that the configured % values
    produce sane dupe yields against the upgrade cost tables."""
    cost_by_rarity: dict[str, list[int]] = {}
    for tbl in config.hero_upgrade_tables:
        cost_by_rarity[tbl.rarity.value] = list(tbl.duplicate_costs)
    if not cost_by_rarity:
        return

    # Pick up to 4 representative card levels spaced across the upgrade table.
    any_costs = next(iter(cost_by_rarity.values()))
    num_levels = len(any_costs)
    if num_levels == 0:
        return
    if num_levels <= 4:
        sample_levels = list(range(1, num_levels + 1))
    else:
        sample_levels = sorted({1, num_levels // 3, (2 * num_levels) // 3, num_levels})

    rows = []
    for rarity in ("GRAY", "BLUE", "GOLD"):
        costs = cost_by_rarity.get(rarity, [])
        if not costs:
            continue
        mn = min_pct_by_rarity.get(rarity, 0.0)
        mx = max_pct_by_rarity.get(rarity, 0.0)
        row: dict[str, str] = {"Rarity": rarity}
        for lvl in sample_levels:
            idx = min(lvl - 1, len(costs) - 1)
            cost = costs[idx]
            row[f"L{lvl} (need {cost})"] = f"{round(cost * mn)}–{round(cost * mx)}"
        rows.append(row)

    if rows:
        st.caption(caption)
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def _render_duplicate_ranges_tab(config: HeroCardConfig) -> None:
    st.subheader("Hero Card Duplicate Ranges (per Rarity)")
    st.caption(
        "When a hero card is pulled, dupes received = round(dupe-cost-for-next-level × random(min%, max%)). "
        "One row per card level. The **Dupes (min–max)** column resolves the % against the upgrade-cost table "
        "so you can sanity-check the actual number of dupes a single pull will deliver."
    )

    if not config.hero_duplicate_ranges:
        st.info("No duplicate ranges configured.")
        return

    rarity_names = [dr.rarity.value for dr in config.hero_duplicate_ranges]
    sel = st.selectbox("Rarity", range(len(rarity_names)), format_func=lambda i: rarity_names[i], key="vb_duperange_rarity")
    dr = config.hero_duplicate_ranges[sel]

    num_levels = len(dr.min_pct)
    coins_list = dr.coins_per_dupe if dr.coins_per_dupe else [5] * num_levels
    while len(coins_list) < num_levels:
        coins_list.append(coins_list[-1] if coins_list else 5)

    # Resolve next-level dupe cost for this rarity (used to preview dupes-per-pull)
    cost_table = next(
        (t.duplicate_costs for t in config.hero_upgrade_tables if t.rarity == dr.rarity),
        [],
    )
    dupe_costs_aligned = list(cost_table[:num_levels])
    while len(dupe_costs_aligned) < num_levels:
        dupe_costs_aligned.append(dupe_costs_aligned[-1] if dupe_costs_aligned else 0)

    preview = [
        f"{round(dupe_costs_aligned[i] * dr.min_pct[i])}–{round(dupe_costs_aligned[i] * dr.max_pct[i])}"
        for i in range(num_levels)
    ]

    df = pd.DataFrame({
        "Card Level": range(1, num_levels + 1),
        "Dupes Needed": dupe_costs_aligned,
        "Min %": [round(v * 100, 1) for v in dr.min_pct],
        "Max %": [round(v * 100, 1) for v in dr.max_pct],
        "Dupes (min–max)": preview,
        "Coins/Dupe": coins_list[:num_levels],
    })
    bulk = render_bulk_edit_bar(f"hero_duperange_{sel}", df, label=f"{rarity_names[sel]} Dupe Ranges")
    if bulk is not None:
        df = bulk
    edited = st.data_editor(
        df,
        column_config={
            "Card Level": st.column_config.NumberColumn("Card Level", disabled=True),
            "Dupes Needed": st.column_config.NumberColumn(
                "Dupes Needed", disabled=True,
                help="Dupes required to reach the next level (from the upgrade cost table). Read-only.",
            ),
            "Min %": st.column_config.NumberColumn("Min %", min_value=0.0, max_value=100.0, step=1.0, format="%.1f"),
            "Max %": st.column_config.NumberColumn("Max %", min_value=0.0, max_value=100.0, step=1.0, format="%.1f"),
            "Dupes (min–max)": st.column_config.TextColumn(
                "Dupes (min–max)", disabled=True,
                help="Resolved dupe range per pull = round(Dupes Needed × Min/Max %). Read-only sanity check.",
            ),
            "Coins/Dupe": st.column_config.NumberColumn("Coins/Dupe", min_value=0, step=1),
        },
        width="stretch",
        hide_index=True,
        num_rows="fixed",
        key=f"vb_duperange_{sel}",
    )
    dr.min_pct = [float(row["Min %"]) / 100.0 for _, row in edited.iterrows()]
    dr.max_pct = [float(row["Max %"]) / 100.0 for _, row in edited.iterrows()]
    dr.coins_per_dupe = [int(row["Coins/Dupe"]) for _, row in edited.iterrows()]


def _render_shared_dupe_ranges_tab(config: HeroCardConfig) -> None:
    st.subheader("Shared Card Duplicate Ranges (per Category)")
    st.caption(
        "When a shared card is pulled, dupes received = round(dupe_cost x random(min%, max%)). "
        "One row per card level. Shared cards grant bluestars but no hero XP."
    )

    if not config.shared_duplicate_ranges:
        st.info("No shared duplicate ranges configured.")
        return

    cat_names = [dr.category for dr in config.shared_duplicate_ranges]
    sel = st.selectbox("Category", range(len(cat_names)), format_func=lambda i: cat_names[i], key="vb_shared_duperange_cat")
    dr = config.shared_duplicate_ranges[sel]

    num_levels = len(dr.min_pct)
    coins_list = dr.coins_per_dupe if dr.coins_per_dupe else [5] * num_levels
    while len(coins_list) < num_levels:
        coins_list.append(coins_list[-1] if coins_list else 5)
    df = pd.DataFrame({
        "Card Level": range(1, num_levels + 1),
        "Min %": [round(v * 100, 1) for v in dr.min_pct],
        "Max %": [round(v * 100, 1) for v in dr.max_pct],
        "Coins/Dupe": coins_list[:num_levels],
    })
    bulk = render_bulk_edit_bar(f"shared_duperange_{sel}", df, label=f"{cat_names[sel]} Shared Dupe Ranges")
    if bulk is not None:
        df = bulk
    edited = st.data_editor(
        df,
        column_config={
            "Card Level": st.column_config.NumberColumn("Card Level", disabled=True),
            "Min %": st.column_config.NumberColumn("Min %", min_value=0.0, max_value=100.0, step=1.0, format="%.1f"),
            "Max %": st.column_config.NumberColumn("Max %", min_value=0.0, max_value=100.0, step=1.0, format="%.1f"),
            "Coins/Dupe": st.column_config.NumberColumn("Coins/Dupe", min_value=0, step=1),
        },
        width="stretch",
        hide_index=True,
        num_rows="fixed",
        key=f"vb_shared_duperange_{sel}",
    )
    dr.min_pct = [float(row["Min %"]) / 100.0 for _, row in edited.iterrows()]
    dr.max_pct = [float(row["Max %"]) / 100.0 for _, row in edited.iterrows()]
    dr.coins_per_dupe = [int(row["Coins/Dupe"]) for _, row in edited.iterrows()]


def _render_pack_bonuses_tab(config: HeroCardConfig) -> None:
    """Editor for per-pack bonus item economy.

    Five tables, all keyed by pack name:
      - Slots + variance multiplier
      - Dupe boost (shared / unique)
      - Drop probability per bonus item
      - Base amount per bonus item
    """
    from simulation.variants.variant_b.pack_bonuses import (
        BONUS_ITEM_KEYS,
        default_pack_bonus_amounts,
        default_pack_bonus_probs,
        default_pack_bonus_slots,
        default_pack_bonus_variance,
        default_pack_dupe_boost,
    )

    st.subheader("Pack Bonuses")
    st.caption(
        "Every regular pack open rolls a number of bonus item slots. Each slot "
        "independently rolls every bonus item type at the configured probability; "
        "rolled items grant `base_amount × uniform(bottom, top)` rounded. Pack "
        "dupe boost multiplies dropped-card duplicates by `1 + boost` (shared / unique)."
    )

    # Backfill on first render if a profile loaded with empty maps.
    if not config.pack_bonus_slots:
        config.pack_bonus_slots = default_pack_bonus_slots()
    if not config.pack_bonus_probs:
        config.pack_bonus_probs = default_pack_bonus_probs()
    if not config.pack_bonus_amounts:
        config.pack_bonus_amounts = default_pack_bonus_amounts()
    if not config.pack_bonus_variance:
        config.pack_bonus_variance = default_pack_bonus_variance()
    if not config.pack_dupe_boost:
        config.pack_dupe_boost = default_pack_dupe_boost()

    pack_names = sorted(set(config.pack_bonus_slots) | set(config.pack_bonus_probs))
    if not pack_names:
        st.info("No packs configured.")
        return

    # ── Slots + variance ────────────────────────────────────────────────────
    st.markdown("**Slots & variance**")
    st.caption(
        "Slots = independent bonus rolls per pack. Variance Bottom/Top bound the "
        "uniform multiplier applied to each rolled base amount."
    )
    rows = []
    for pack in pack_names:
        var = config.pack_bonus_variance.get(pack, [1.0, 1.0])
        rows.append({
            "Pack": pack,
            "Slots": int(config.pack_bonus_slots.get(pack, 0)),
            "Variance Bottom": float(var[0]) if len(var) > 0 else 1.0,
            "Variance Top": float(var[1]) if len(var) > 1 else 1.0,
        })
    slots_df = pd.DataFrame(rows)
    bulk = render_bulk_edit_bar("pack_bonus_slots", slots_df, label="Pack Bonus Slots & Variance")
    if bulk is not None:
        slots_df = bulk
    edited_slots = st.data_editor(
        slots_df,
        column_config={
            "Pack": st.column_config.TextColumn("Pack", disabled=True),
            "Slots": st.column_config.NumberColumn("Slots", min_value=0, max_value=20, step=1),
            "Variance Bottom": st.column_config.NumberColumn("Bottom", min_value=0.0, max_value=5.0, step=0.05, format="%.2f"),
            "Variance Top": st.column_config.NumberColumn("Top", min_value=0.0, max_value=5.0, step=0.05, format="%.2f"),
        },
        width="stretch",
        hide_index=True,
        num_rows="fixed",
        key="vb_pack_bonus_slots_table",
    )
    new_slots: dict[str, int] = {}
    new_variance: dict[str, list[float]] = {}
    for _, row in edited_slots.iterrows():
        pack = str(row["Pack"])
        new_slots[pack] = int(row["Slots"])
        bot = float(row["Variance Bottom"])
        top = float(row["Variance Top"])
        if top < bot:
            top = bot
        new_variance[pack] = [bot, top]
    config.pack_bonus_slots = new_slots
    config.pack_bonus_variance = new_variance

    st.divider()

    # ── Dupe boost ──────────────────────────────────────────────────────────
    st.markdown("**Dupe boost** (applied to dropped card duplicates)")
    st.caption(
        "`final_dupes = round(base_dupes × (1 + boost))`. Shared boost affects "
        "shared/gold/blue/gray cards; unique boost affects hero-unique cards."
    )
    boost_rows = []
    for pack in pack_names:
        b = config.pack_dupe_boost.get(pack, [0.0, 0.0])
        boost_rows.append({
            "Pack": pack,
            "Shared boost %": round(float(b[0]) * 100, 1) if len(b) > 0 else 0.0,
            "Unique boost %": round(float(b[1]) * 100, 1) if len(b) > 1 else 0.0,
        })
    boost_df = pd.DataFrame(boost_rows)
    bulk = render_bulk_edit_bar("pack_dupe_boost", boost_df, label="Pack Dupe Boost")
    if bulk is not None:
        boost_df = bulk
    edited_boost = st.data_editor(
        boost_df,
        column_config={
            "Pack": st.column_config.TextColumn("Pack", disabled=True),
            "Shared boost %": st.column_config.NumberColumn("Shared boost %", min_value=0.0, max_value=500.0, step=5.0, format="%.1f"),
            "Unique boost %": st.column_config.NumberColumn("Unique boost %", min_value=0.0, max_value=500.0, step=5.0, format="%.1f"),
        },
        width="stretch",
        hide_index=True,
        num_rows="fixed",
        key="vb_pack_dupe_boost_table",
    )
    new_boost: dict[str, list[float]] = {}
    for _, row in edited_boost.iterrows():
        new_boost[str(row["Pack"])] = [
            float(row["Shared boost %"]) / 100.0,
            float(row["Unique boost %"]) / 100.0,
        ]
    config.pack_dupe_boost = new_boost

    st.divider()

    # ── Drop probabilities ──────────────────────────────────────────────────
    st.markdown("**Drop probabilities (per slot, per item)**")
    st.caption("Each slot rolls every item independently at this probability.")
    item_cols = [k for k in BONUS_ITEM_KEYS if k != "PurpleStars"]
    prob_rows = []
    for pack in pack_names:
        per_pack = config.pack_bonus_probs.get(pack, {})
        row = {"Pack": pack}
        for item in item_cols:
            row[item] = round(float(per_pack.get(item, 0.0)) * 100, 1)
        prob_rows.append(row)
    prob_df = pd.DataFrame(prob_rows)
    bulk = render_bulk_edit_bar("pack_bonus_probs", prob_df, label="Pack Bonus Drop Probabilities (%)")
    if bulk is not None:
        prob_df = bulk
    prob_col_config = {"Pack": st.column_config.TextColumn("Pack", disabled=True)}
    for item in item_cols:
        prob_col_config[item] = st.column_config.NumberColumn(
            item, min_value=0.0, max_value=100.0, step=1.0, format="%.1f",
        )
    edited_probs = st.data_editor(
        prob_df, column_config=prob_col_config,
        width="stretch", hide_index=True, num_rows="fixed",
        key="vb_pack_bonus_probs_table",
    )
    new_probs: dict[str, dict[str, float]] = {}
    for _, row in edited_probs.iterrows():
        pack = str(row["Pack"])
        new_probs[pack] = {
            item: float(row[item]) / 100.0
            for item in item_cols
            if item in row
        }
    config.pack_bonus_probs = new_probs

    st.divider()

    # ── Base amounts ────────────────────────────────────────────────────────
    st.markdown("**Base amounts (per item, per pack)**")
    st.caption(
        "When an item drops, the player receives `round(base_amount × uniform(bottom, top))`."
    )
    amt_rows = []
    for pack in pack_names:
        per_pack = config.pack_bonus_amounts.get(pack, {})
        row = {"Pack": pack}
        for item in item_cols:
            row[item] = int(per_pack.get(item, 0))
        amt_rows.append(row)
    amt_df = pd.DataFrame(amt_rows)
    bulk = render_bulk_edit_bar("pack_bonus_amounts", amt_df, label="Pack Bonus Base Amounts")
    if bulk is not None:
        amt_df = bulk
    amt_col_config = {"Pack": st.column_config.TextColumn("Pack", disabled=True)}
    for item in item_cols:
        amt_col_config[item] = st.column_config.NumberColumn(
            item, min_value=0, max_value=100000, step=5, format="%d",
        )
    edited_amts = st.data_editor(
        amt_df, column_config=amt_col_config,
        width="stretch", hide_index=True, num_rows="fixed",
        key="vb_pack_bonus_amts_table",
    )
    new_amts: dict[str, dict[str, int]] = {}
    for _, row in edited_amts.iterrows():
        pack = str(row["Pack"])
        new_amts[pack] = {
            item: int(row[item])
            for item in item_cols
            if item in row
        }
    config.pack_bonus_amounts = new_amts


def _render_pack_schedule_tab(config: HeroCardConfig) -> None:
    # --- Pack type definitions ---
    st.subheader("Pack Types")
    st.caption(
        "Define pack types and their card-yield progression. "
        "Card types scale with total unlocked cards (floor-matched). "
        "The daily schedule references these by name."
    )

    if not config.pack_types:
        config.pack_types = [
            HeroPackType(name="StandardPack", card_types_table={0: HeroCardTypesRange(min=1, max=3)}),
        ]

    # Pack name editor
    pack_names_df = pd.DataFrame([{"Name": pt.name} for pt in config.pack_types])
    edited_names = st.data_editor(
        pack_names_df,
        column_config={"Name": st.column_config.TextColumn("Pack Type Name")},
        width="stretch",
        hide_index=True,
        num_rows="dynamic",
        key="vb_pack_type_names",
    )
    new_names = [str(row["Name"]).strip() for _, row in edited_names.iterrows() if str(row.get("Name", "")).strip()]

    # Sync pack_types list with edited names (preserve existing tables, add empty for new)
    existing_map = {pt.name: pt for pt in config.pack_types}
    config.pack_types = [
        existing_map.get(name, HeroPackType(name=name, card_types_table={0: HeroCardTypesRange(min=1, max=2)}))
        for name in new_names
    ]
    # Update names in case of renames
    for pt, name in zip(config.pack_types, new_names):
        pt.name = name

    # Per-pack card_types_table editors
    if config.pack_types:
        st.markdown("**Card Types Tables by Pack**")
        st.caption("Maps total unlocked card count to min/max card types yielded per pack opening.")
        pack_tabs = st.tabs([pt.name for pt in config.pack_types])
        for pt, tab in zip(config.pack_types, pack_tabs):
            with tab:
                table_data = [
                    {"Unlocked Card Count": int(k), "Min Card Types": int(v.min), "Max Card Types": int(v.max)}
                    for k, v in sorted(pt.card_types_table.items(), key=lambda x: int(x[0]))
                ]
                if not table_data:
                    table_data = [{"Unlocked Card Count": 0, "Min Card Types": 1, "Max Card Types": 2}]

                ct_df = pd.DataFrame(table_data)
                edited_ct = st.data_editor(
                    ct_df,
                    column_config={
                        "Unlocked Card Count": st.column_config.NumberColumn(
                            "Unlocked Card Count", min_value=0, step=1, format="%d", required=True,
                        ),
                        "Min Card Types": st.column_config.NumberColumn(
                            "Min Card Types", min_value=1, max_value=20, step=1, format="%d", required=True,
                        ),
                        "Max Card Types": st.column_config.NumberColumn(
                            "Max Card Types", min_value=1, max_value=20, step=1, format="%d", required=True,
                        ),
                    },
                    hide_index=True,
                    width="stretch",
                    num_rows="dynamic",
                    key=f"vb_card_types_{pt.name}",
                )
                pt.card_types_table = {
                    int(row._1): HeroCardTypesRange(min=int(row._2), max=int(row._3))
                    for row in edited_ct.itertuples()
                }

    st.divider()

    # --- Daily schedule ---
    st.subheader("Daily Pack Schedule")
    st.caption("Expected pack count per type per day. Schedule repeats cyclically.")
    if config.daily_pack_schedule:
        sched_df = pd.DataFrame(config.daily_pack_schedule)
        sched_df.insert(0, "Day", range(1, len(sched_df) + 1))
        bulk = render_bulk_edit_bar("daily_pack_sched", sched_df, label="Daily Pack Schedule")
        if bulk is not None:
            sched_df = bulk
        edited = st.data_editor(sched_df, width="stretch", hide_index=True, num_rows="dynamic", key="vb_daily_packs")
        config.daily_pack_schedule = [
            {col: float(row[col]) for col in edited.columns if col != "Day"}
            for _, row in edited.iterrows()
        ]
    else:
        st.info("No daily pack schedule configured. Add pack types above first.")

    st.divider()
    st.subheader("Simulated Premium Purchases")
    st.caption("How many premium packs the simulated player buys per day cycle.")
    if config.premium_pack_purchase_schedule:
        purch_df = pd.DataFrame(config.premium_pack_purchase_schedule)
        purch_df.insert(0, "Day", range(1, len(purch_df) + 1))
        bulk = render_bulk_edit_bar("pp_purchases", purch_df, label="Premium Purchases")
        if bulk is not None:
            purch_df = bulk
        edited = st.data_editor(purch_df, width="stretch", hide_index=True, num_rows="dynamic", key="vb_pp_purchases")
        config.premium_pack_purchase_schedule = [
            {col: int(row[col]) for col in edited.columns if col != "Day"}
            for _, row in edited.iterrows()
        ]


def _render_profiles_tab(config: HeroCardConfig) -> None:
    st.subheader("User Profiles")
    st.caption("Save and load full Hero Card System configurations.")

    profiles = list_vb_profiles()
    if profiles:
        selected = st.selectbox("Select Profile", profiles, key="vb_profile_select")
        col_load, col_del = st.columns(2)
        with col_load:
            if st.button("Load Profile", key="vb_load_profile", icon=":material/folder_open:"):
                profile = load_vb_profile(selected)
                if profile.full_config is not None:
                    loaded = HeroCardConfig.model_validate(profile.full_config)
                    for field in loaded.model_fields:
                        setattr(config, field, getattr(loaded, field))
                st.rerun()
        with col_del:
            if st.button("Delete Profile", key="vb_del_profile", icon=":material/delete:"):
                delete_vb_profile(selected)
                st.rerun()
    else:
        st.info("No saved profiles yet.")

    st.divider()
    new_name = st.text_input("Profile Name", key="vb_new_profile_name")
    if st.button("Save Profile", key="vb_save_profile", icon=":material/save:"):
        if new_name.strip():
            config_dict = json.loads(config.model_dump_json())
            profile = UserProfile(
                name=new_name.strip(),
                full_config=config_dict,
            )
            save_vb_profile(profile)
            st.success(f"Saved profile '{new_name.strip()}'")
            st.rerun()
        else:
            st.warning("Enter a profile name.")


def _render_import_export(config: HeroCardConfig) -> None:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Export")
        st.download_button(
            "Download Config JSON",
            data=config.model_dump_json(indent=2),
            file_name="hero_card_config.json",
            mime="application/json",
            width="stretch",
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
