"""Variant B config editor — Hero Card System.

Every parameter is editable from the frontend: heroes, card pools, skill trees,
XP tables, upgrade costs, premium packs, drop algorithm settings, joker rates.
"""

import json

import pandas as pd
import streamlit as st

from app_pages.bulk_edit_helpers import render_bulk_edit_bar
from simulation.variants.variant_b.models import (
    HeroCardConfig,
    HeroCardDef,
    HeroCardRarity,
    HeroDef,
    HeroUpgradeCostTable,
    PackVariant,
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
        "Hero Packs",
        "Pack Variants",
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
        _render_pack_variants_tab(config)
    with tabs[8]:
        _render_pack_schedule_tab(config)
    with tabs[9]:
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

            bulk = render_bulk_edit_bar(f"hero_cards_{selected_idx}", card_df, label=f"{hero.name} Card Pool")
            if bulk is not None:
                card_df = bulk

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
    st.subheader("Drop Algorithm")
    dc = config.drop_config

    # --- Controls ---
    col1, col2 = st.columns(2)
    with col1:
        dc.hero_vs_shared_base_rate = st.slider(
            "Hero vs Shared base rate",
            min_value=0.0, max_value=1.0, value=dc.hero_vs_shared_base_rate, step=0.05,
            help="Probability of pulling a hero card vs shared card",
            key="vb_hero_rate",
        )
    with col2:
        dc.pity_counter_threshold = st.number_input(
            "Pity counter (0 = disabled)",
            min_value=0, max_value=100, value=dc.pity_counter_threshold, step=1,
            help="Guarantee hero card after N shared-only pulls",
            key="vb_pity",
        )

    st.markdown("##### Hero bucket selection")
    st.caption("Heroes ranked by level, split into 3 tiers")
    b1, b2, b3 = st.columns(3)
    with b1:
        dc.bucket_bottom_weight = st.slider(
            "Bottom bucket", min_value=0.0, max_value=1.0,
            value=dc.bucket_bottom_weight, step=0.05, key="vb_bkt_bot",
        )
    with b2:
        dc.bucket_middle_weight = st.slider(
            "Middle bucket", min_value=0.0, max_value=1.0,
            value=dc.bucket_middle_weight, step=0.05, key="vb_bkt_mid",
        )
    with b3:
        dc.bucket_top_weight = st.slider(
            "Top bucket", min_value=0.0, max_value=1.0,
            value=dc.bucket_top_weight, step=0.05, key="vb_bkt_top",
        )
    bucket_sum = dc.bucket_bottom_weight + dc.bucket_middle_weight + dc.bucket_top_weight
    if abs(bucket_sum - 1.0) > 0.01:
        st.warning(f"Bucket weights sum to {bucket_sum:.2f} — should be 1.0")

    st.markdown("##### Rarity weights")
    r1, r2, r3 = st.columns(3)
    with r1:
        dc.rarity_weight_common = st.slider(
            "Common", min_value=0.0, max_value=1.0,
            value=dc.rarity_weight_common, step=0.01, key="vb_rw_c",
        )
    with r2:
        dc.rarity_weight_rare = st.slider(
            "Rare", min_value=0.0, max_value=1.0,
            value=dc.rarity_weight_rare, step=0.01, key="vb_rw_r",
        )
    with r3:
        dc.rarity_weight_epic = st.slider(
            "Epic", min_value=0.0, max_value=1.0,
            value=dc.rarity_weight_epic, step=0.01, key="vb_rw_e",
        )
    rarity_sum = dc.rarity_weight_common + dc.rarity_weight_rare + dc.rarity_weight_epic
    if abs(rarity_sum - 1.0) > 0.01:
        st.warning(f"Rarity weights sum to {rarity_sum:.2f} — should be 1.0")

    st.markdown("##### Anti-streak decay")
    s1, s2 = st.columns(2)
    with s1:
        dc.streak_decay_shared = st.number_input(
            "Shared streak decay", min_value=0.0, max_value=1.0,
            value=dc.streak_decay_shared, step=0.05, key="vb_sd_shared",
        )
    with s2:
        dc.streak_decay_hero = st.number_input(
            "Hero streak decay", min_value=0.0, max_value=1.0,
            value=dc.streak_decay_hero, step=0.05,
            help="Multiplier per consecutive same-hero pull (lower = stronger penalty)",
            key="vb_sd_hero",
        )

    # --- Live diagram ---
    st.divider()
    _render_drop_diagram(config)


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
    st.subheader("Hero Card Packs")
    st.caption("Each hero has one card pack. Select a hero to edit its card drop rates.")

    if not config.premium_packs:
        st.info("No hero packs configured.")
        return

    # Build hero name lookup
    hero_name_map = {h.hero_id: h.name for h in config.heroes}
    pack_labels = [hero_name_map.get(p.featured_hero_ids[0], p.name) if p.featured_hero_ids else p.name for p in config.premium_packs]
    sel = st.selectbox("Select hero", range(len(pack_labels)), format_func=lambda i: pack_labels[i], key="vb_ppack_sel")
    pack = config.premium_packs[sel]

    st.markdown("**Per-card drop rates**")
    if pack.card_drop_rates:
        # Build card name lookup
        card_names = {}
        for hero in config.heroes:
            for card in hero.card_pool:
                card_names[card.card_id] = f"{card.name} ({card.rarity.value})"

        rates_df = pd.DataFrame([
            {"Card": card_names.get(r.card_id, r.card_id), "Card ID": r.card_id, "Drop Rate": r.drop_rate}
            for r in pack.card_drop_rates
        ])
        edited = st.data_editor(
            rates_df,
            column_config={
                "Card": st.column_config.TextColumn("Card", disabled=True),
                "Card ID": st.column_config.TextColumn("Card ID", disabled=True),
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


def _render_pack_variants_tab(config: HeroCardConfig) -> None:
    st.subheader("Pack Variants")
    st.caption("5 bonus tiers applied to any hero pack. Edit costs, cards per pack, joker rates, and dupe multipliers.")

    if not config.pack_variants:
        st.info("No pack variants configured.")
        return

    rows = [
        {
            "Tier": v.tier.value,
            "Diamond Cost": v.diamond_cost,
            "Cards per Pack": v.cards_per_pack,
            "Joker Rate %": round(v.joker_rate * 100, 1),
            "Dupe Multiplier": v.dupe_boost_multiplier,
        }
        for v in config.pack_variants
    ]
    df = pd.DataFrame(rows)
    edited = st.data_editor(
        df,
        column_config={
            "Tier": st.column_config.TextColumn("Tier", disabled=True),
            "Diamond Cost": st.column_config.NumberColumn("Diamond Cost", min_value=0, step=50),
            "Cards per Pack": st.column_config.NumberColumn("Cards per Pack", min_value=1, max_value=50, step=1),
            "Joker Rate %": st.column_config.NumberColumn("Joker Rate %", min_value=0.0, max_value=30.0, step=0.5, format="%.1f"),
            "Dupe Multiplier": st.column_config.NumberColumn("Dupe Multiplier", min_value=0.5, max_value=10.0, step=0.1, format="%.1f"),
        },
        use_container_width=True,
        hide_index=True,
        key="vb_pack_variants",
    )
    for i, (_, row) in enumerate(edited.iterrows()):
        if i < len(config.pack_variants):
            config.pack_variants[i].diamond_cost = int(row["Diamond Cost"])
            config.pack_variants[i].cards_per_pack = int(row["Cards per Pack"])
            config.pack_variants[i].joker_rate = float(row["Joker Rate %"]) / 100.0
            config.pack_variants[i].dupe_boost_multiplier = float(row["Dupe Multiplier"])


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


def _render_drop_diagram(config: HeroCardConfig) -> None:
    """Render a clean flowchart of the bucket-based drop algorithm."""
    dc = config.drop_config
    hero_pct = f"{dc.hero_vs_shared_base_rate * 100:.0f}"
    shared_pct = f"{(1 - dc.hero_vs_shared_base_rate) * 100:.0f}"
    pity = dc.pity_counter_threshold
    bot = f"{dc.bucket_bottom_weight * 100:.0f}"
    mid = f"{dc.bucket_middle_weight * 100:.0f}"
    top_w = f"{dc.bucket_top_weight * 100:.0f}"
    rc = f"{dc.rarity_weight_common * 100:.0f}"
    rr = f"{dc.rarity_weight_rare * 100:.0f}"
    re = f"{dc.rarity_weight_epic * 100:.0f}"
    streak = dc.streak_decay_hero
    gold = config.num_gold_cards
    blue = config.num_blue_cards

    html = f"""
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
.d{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
    max-width:680px;margin:24px auto;color:#e8e8e8}}
.n{{border-radius:10px;padding:16px 20px;margin:12px auto;text-align:center;
    font-size:15px;line-height:1.6;max-width:560px}}
.n b{{font-size:16px}}
.start{{background:#0d1b2a;border:2px solid #4a90d9}}
.decide{{background:#1b1b35;border:2px solid #f5a623}}
.step{{background:#0f2318;border:2px solid #4caf50}}
.result{{background:#2a0f0f;border:2px solid #ef5350}}
.arr{{text-align:center;font-size:28px;color:#666;margin:4px 0;line-height:1}}
.arr span{{font-size:13px;color:#999;display:block;margin-top:-2px}}
.split{{display:flex;gap:20px;margin:12px 0}}
.split>div{{flex:1}}
.tag{{display:inline-block;padding:3px 10px;border-radius:12px;font-size:12px;
     font-weight:700;margin:2px 3px}}
.t-hero{{background:#e65100;color:#fff}}
.t-shared{{background:#1565c0;color:#fff}}
.t-pity{{background:#c62828;color:#fff}}
.t-bkt{{background:#00695c;color:#fff}}
.t-cmn{{background:#616161;color:#fff}}
.t-rare{{background:#1565c0;color:#fff}}
.t-epic{{background:#6a1b9a;color:#fff}}
.sub{{font-size:13px;color:#aaa;margin-top:6px}}
</style>
<div class="d">

<div class="n start"><b>REGULAR PACK PULL</b></div>
<div class="arr">\u2193</div>

<div class="n decide">
  <b>PITY CHECK</b><br>
  {pity}+ shared pulls without hero card?<br>
  <span class="sub">Yes \u2192 force hero card &nbsp;|&nbsp; No \u2192 roll normally</span>
</div>
<div class="arr">\u2193</div>

<div class="n decide">
  <b>HERO vs SHARED</b><br>
  <span class="tag t-hero">Hero {hero_pct}%</span>
  <span class="tag t-shared">Shared {shared_pct}%</span>
</div>

<div class="split">
<div>
  <div class="arr">\u2193<span>Hero card</span></div>
  <div class="n step"><b>1. Pick bucket</b><br>
    <span class="tag t-bkt">Bottom {bot}%</span>
    <span class="tag t-bkt">Mid {mid}%</span>
    <span class="tag t-bkt">Top {top_w}%</span><br>
    <span class="sub">Heroes ranked by level \u2192 3 tiers</span>
  </div>
  <div class="arr">\u2193</div>
  <div class="n step"><b>2. Pick hero</b><br>
    <span class="sub">Anti-streak: \u00d7{streak} per consecutive same-hero</span>
  </div>
  <div class="arr">\u2193</div>
  <div class="n step"><b>3. Roll rarity</b><br>
    <span class="tag t-cmn">Common {rc}%</span>
    <span class="tag t-rare">Rare {rr}%</span>
    <span class="tag t-epic">Epic {re}%</span>
  </div>
  <div class="arr">\u2193</div>
  <div class="n step"><b>4. Pick card</b><br>
    <span class="sub">Lowest-level-first catch-up</span>
  </div>
  <div class="arr">\u2193</div>
  <div class="n step"><b>5. Compute dupes</b><br>
    <span class="sub">max(1, 4 \u2212 level\u00f710) \u2192 random 1..base</span>
  </div>
  <div class="arr">\u2193</div>
  <div class="n result"><b>UPGRADE</b><br>
    <span class="sub">Dupes + Coins \u2192 Level up \u2192 Bluestars + Hero XP<br>Pity counter resets</span>
  </div>
</div>
<div>
  <div class="arr">\u2193<span>Shared card</span></div>
  <div class="n step"><b>Pick shared card</b><br>
    <span class="sub">Lowest-level-first catch-up<br>{gold} Gold + {blue} Blue cards</span>
  </div>
  <div class="arr">\u2193</div>
  <div class="n result"><b>STANDARD UPGRADE</b><br>
    <span class="sub">Same upgrade engine<br>Pity counter +1</span>
  </div>
</div>
</div>

<div style="margin-top:20px;padding:14px 18px;border-radius:10px;background:#1a1028;border:2px solid #7b1fa2;max-width:560px;margin-left:auto;margin-right:auto;text-align:center">
  <b>JOKERS</b> \u2014 only from <b>hero-specific premium packs</b><br>
  <span class="sub">Each premium pack has its own joker rate (configured in Premium Packs tab).<br>
  Jokers are universal wildcards that upgrade any hero card.</span>
</div>

</div>
"""
    st.components.v1.html(html, height=980, scrolling=False)
