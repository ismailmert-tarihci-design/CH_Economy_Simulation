"""Card Drop Simulator.

Pulls a fixed number of cards per day using the real Variant B card-drop
algorithm (hero-vs-shared decision, bucket/anti-streak hero selection, shared
top-K catch-up), applies duplicates + coin income, runs the daily upgrade pass
to accrue bluestars, and reads out **daily power** from the bluestar→power
curve (editable in Configuration → Power curve).

Unlike the day-by-day simulator this tool ignores the daily pack schedule and
premium purchases — it answers the narrow question "if a player pulls X cards a
day, how do bluestars and power grow?"
"""

from __future__ import annotations

from random import Random

import pandas as pd
import streamlit as st

from simulation.variants.variant_b.models import HeroCardConfig
from simulation.variants.variant_b.orchestrator import _create_initial_state
from simulation.variants.variant_b.hero_deck import unlock_heroes_by_day
from simulation.variants.variant_b.drop_algorithm import (
    compute_hero_duplicates,
    compute_shared_duplicates,
    decide_hero_or_shared,
    get_coins_per_dupe,
    get_shared_coins_per_dupe,
    select_hero_card,
    select_shared_card,
)
from simulation.variants.variant_b.upgrade_engine import (
    attempt_hero_upgrades,
    attempt_shared_upgrades,
)
from simulation.variants.variant_b.power_curve import (
    power_for_bluestars,
    resolve_power_table,
)


def render_card_drop_simulator() -> None:
    st.title("Card Drop Simulator")
    st.caption(
        "Pull a fixed number of cards per day through the real card-drop algorithm, "
        "apply duplicates and upgrades, and track daily power from the bluestar→power curve."
    )

    variant_id = st.session_state.get("active_variant", "variant_b")
    if variant_id != "variant_b":
        st.info("Switch to **Hero Card System** variant in the sidebar to use this tool.")
        return

    config: HeroCardConfig = st.session_state.configs.get("variant_b")
    if config is None:
        st.warning("No Variant B config loaded.")
        return

    # --- Controls ---
    c1, c2, c3 = st.columns(3)
    with c1:
        cards_per_day = st.number_input(
            "Cards pulled per day", min_value=1, max_value=5000, value=50, step=5,
            key="cds_cards_per_day",
        )
    with c2:
        num_days = st.number_input(
            "Days to simulate", min_value=1, max_value=730, value=90, step=1,
            key="cds_num_days",
        )
    with c3:
        seed = st.number_input(
            "RNG seed (0 = random)", min_value=0, max_value=999999, value=0,
            key="cds_seed",
        )

    c4, c5 = st.columns(2)
    with c4:
        start_day = st.number_input(
            "Starting calendar day", min_value=1, max_value=802, value=1, step=1,
            help="Heroes unlock on a fixed calendar (Woody day 0 … Munara day 802). "
                 "Start later to begin with more heroes already unlocked.",
            key="cds_start_day",
        )
    with c5:
        run_upgrades = st.checkbox(
            "Run daily upgrades (accrue bluestars/power)", value=True,
            help="Greedily spend duplicates + coins on upgrades each day. Bluestars — "
                 "and therefore power — only grow when upgrades happen.",
            key="cds_run_upgrades",
        )

    st.caption(
        f"**{int(cards_per_day * num_days):,}** total card pulls over **{num_days}** days "
        f"(calendar day {start_day} → {start_day + num_days - 1})."
    )

    if st.button("Run simulation", type="primary", width="stretch", key="cds_run"):
        rng = Random(seed if seed > 0 else None)
        with st.spinner("Pulling cards…"):
            rows = _simulate(config, int(cards_per_day), int(num_days), int(start_day), rng, run_upgrades)
        st.session_state["cds_last_rows"] = rows

    rows = st.session_state.get("cds_last_rows")
    if rows:
        _display(rows)


def _simulate(
    config: HeroCardConfig,
    cards_per_day: int,
    num_days: int,
    start_day: int,
    rng: Random,
    run_upgrades: bool,
) -> list[dict]:
    """Run the day loop: X pulls/day → dupes + coins → upgrades → power read-out."""
    state = _create_initial_state(config)
    state.coins = config.initial_coins
    table = resolve_power_table(config)

    rows: list[dict] = []
    for d in range(1, num_days + 1):
        calendar_day = start_day + d - 1
        state.day = calendar_day
        unlock_heroes_by_day(state, config)

        bs_start = state.total_bluestars
        coins_start = state.coins
        hero_pulls = 0
        shared_pulls = 0
        rarity_counts = {"GRAY": 0, "BLUE": 0, "GOLD": 0}

        for i in range(cards_per_day):
            pull_type = decide_hero_or_shared(state, config, rng, pull_index=i)
            if pull_type == "hero":
                result = select_hero_card(state, config, rng)
                if not result:
                    continue
                hero_id, card_id = result
                card = state.heroes[hero_id].cards.get(card_id)
                if not card:
                    continue
                dupes = compute_hero_duplicates(card.level, card.rarity, config, rng)
                card.duplicates += dupes
                cpd = get_coins_per_dupe(card.level, card.rarity, config)
                state.coins += max(1, dupes * cpd)
                hero_pulls += 1
                rarity_key = card.rarity.value if hasattr(card.rarity, "value") else str(card.rarity)
                rarity_counts[rarity_key] = rarity_counts.get(rarity_key, 0) + 1
            else:
                card = select_shared_card(state, config, rng)
                if not card:
                    continue
                cat = card.category.value if hasattr(card.category, "value") else str(card.category)
                dupes = compute_shared_duplicates(card.level, cat, config, rng)
                card.duplicates += dupes
                cpd = get_shared_coins_per_dupe(card.level, cat, config)
                state.coins += max(1, dupes * cpd)
                shared_pulls += 1

        if run_upgrades:
            attempt_hero_upgrades(state, config)
            attempt_shared_upgrades(state, config)

        power = power_for_bluestars(state.total_bluestars, table)
        rows.append({
            "Day": d,
            "Calendar day": calendar_day,
            "Heroes unlocked": len(state.heroes),
            "Hero pulls": hero_pulls,
            "Shared pulls": shared_pulls,
            "Gray": rarity_counts["GRAY"],
            "Blue": rarity_counts["BLUE"],
            "Gold": rarity_counts["GOLD"],
            "Coins balance": state.coins,
            "Coins earned": state.coins - coins_start,
            "Bluestars earned": state.total_bluestars - bs_start,
            "Total bluestars": state.total_bluestars,
            "Power": power,
        })
    return rows


def _display(rows: list[dict]) -> None:
    df = pd.DataFrame(rows)
    last = rows[-1]

    st.markdown("---")
    st.subheader("Summary")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Days simulated", len(rows))
    m2.metric("Total card pulls", f"{int(df['Hero pulls'].sum() + df['Shared pulls'].sum()):,}")
    m3.metric("Final bluestars", f"{int(last['Total bluestars']):,}")
    m4.metric("Final power", f"{last['Power']:,.2f}×")

    n1, n2, n3 = st.columns(3)
    total_pulls = int(df["Hero pulls"].sum() + df["Shared pulls"].sum()) or 1
    n1.metric("Hero pulls", f"{int(df['Hero pulls'].sum()):,}",
              help=f"{df['Hero pulls'].sum() / total_pulls * 100:.0f}% of pulls")
    n2.metric("Shared pulls", f"{int(df['Shared pulls'].sum()):,}",
              help=f"{df['Shared pulls'].sum() / total_pulls * 100:.0f}% of pulls")
    n3.metric("Coins balance", f"{int(last['Coins balance']):,}")

    st.markdown("**Power over time**")
    st.line_chart(df, x="Day", y="Power", height=260)

    st.markdown("**Total bluestars over time**")
    st.line_chart(df, x="Day", y="Total bluestars", height=260)

    with st.expander("Per-day detail", expanded=False):
        st.dataframe(
            df,
            hide_index=True,
            width="stretch",
            column_config={
                "Power": st.column_config.NumberColumn("Power ×", format="%.2f"),
                "Coins balance": st.column_config.NumberColumn(format="%d"),
                "Total bluestars": st.column_config.NumberColumn(format="%d"),
            },
        )
