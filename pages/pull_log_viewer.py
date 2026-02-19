"""Pull-by-pull log viewer for inspecting every card drop and upgrade event."""

from collections import defaultdict
from typing import Any, List

import pandas as pd
import streamlit as st


def render_pull_log_viewer() -> None:
    if "sim_result" not in st.session_state:
        st.warning("No simulation results available. Run a simulation first.")
        return

    result = st.session_state.sim_result
    mode = st.session_state.get("sim_mode", "deterministic")

    if mode != "deterministic":
        st.info("Pull logs are only available for deterministic simulations.")
        return

    pull_logs: List[Any] = getattr(result, "pull_logs", [])
    if not pull_logs:
        st.warning("No pull logs found. Re-run the simulation to generate logs.")
        return

    st.title("Pull-by-Pull Log Viewer")

    _render_summary(pull_logs)
    st.divider()

    view_tab, card_tab = st.tabs(["Chronological View", "Per-Card Breakdown"])

    with view_tab:
        _render_chronological(pull_logs)

    with card_tab:
        _render_per_card(pull_logs)


def _render_summary(pull_logs: list) -> None:
    total_pulls = len(pull_logs)
    total_upgrades = sum(len(p.upgrades) for p in pull_logs)
    unique_cards = set(p.card_id for p in pull_logs)
    max_day = max(p.day for p in pull_logs) if pull_logs else 0

    cols = st.columns(4)
    cols[0].metric("Total Pulls", f"{total_pulls:,}")
    cols[1].metric("Total Upgrades", f"{total_upgrades:,}")
    cols[2].metric("Cards Seen", len(unique_cards))
    cols[3].metric("Days Simulated", max_day)


def _render_chronological(pull_logs: list) -> None:
    max_day = max(p.day for p in pull_logs) if pull_logs else 1

    col1, col2 = st.columns(2)
    with col1:
        day_range = st.slider(
            "Day Range",
            min_value=1,
            max_value=max_day,
            value=(1, min(5, max_day)),
            key="chrono_day_range",
        )
    with col2:
        category_filter = st.multiselect(
            "Category Filter",
            ["GOLD_SHARED", "BLUE_SHARED", "UNIQUE"],
            default=["GOLD_SHARED", "BLUE_SHARED", "UNIQUE"],
            key="chrono_cat_filter",
        )

    filtered = [
        p
        for p in pull_logs
        if day_range[0] <= p.day <= day_range[1] and p.card_category in category_filter
    ]

    if not filtered:
        st.info("No pulls match the filter.")
        return

    rows = []
    for p in filtered:
        upgrade_str = ""
        if p.upgrades:
            parts = [
                f"{u.card_id} L{u.old_level}\u2192{u.new_level}" for u in p.upgrades
            ]
            upgrade_str = "; ".join(parts)

        rows.append(
            {
                "Day": p.day,
                "Pull#": p.pull_index,
                "Card": p.card_name,
                "Category": p.card_category,
                "Level": p.card_level_before,
                "Dupes": f"+{p.duplicates_received}",
                "Total Dupes": p.duplicates_total_after,
                "Coins": p.coins_earned,
                "Upgrades": upgrade_str,
            }
        )

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(
        f"Showing {len(filtered)} pulls from day {day_range[0]} to {day_range[1]}"
    )


def _render_per_card(pull_logs: list) -> None:
    cards_by_category: dict[str, dict[str, list]] = {
        "GOLD_SHARED": defaultdict(list),
        "BLUE_SHARED": defaultdict(list),
        "UNIQUE": defaultdict(list),
    }

    for p in pull_logs:
        cards_by_category[p.card_category][p.card_id].append(p)

    category_tabs = st.tabs(["Gold Shared", "Blue Shared", "Unique"])
    category_keys = ["GOLD_SHARED", "BLUE_SHARED", "UNIQUE"]

    for tab, cat_key in zip(category_tabs, category_keys):
        with tab:
            card_dict = cards_by_category[cat_key]
            if not card_dict:
                st.info(f"No {cat_key} pulls recorded.")
                continue

            sorted_ids = sorted(card_dict.keys())
            selected_card = st.selectbox(
                "Select Card",
                sorted_ids,
                format_func=lambda cid: _card_display_name(card_dict, cid),
                key=f"card_select_{cat_key}",
            )

            if selected_card:
                _render_card_detail(card_dict[selected_card])


def _card_display_name(card_dict: dict, card_id: str) -> str:
    pulls = card_dict[card_id]
    if pulls:
        return f"{pulls[0].card_name} ({len(pulls)} pulls)"
    return card_id


def _render_card_detail(pulls: list) -> None:
    total_dupes = sum(p.duplicates_received for p in pulls)
    total_coins = sum(p.coins_earned for p in pulls)
    upgrades = [u for p in pulls for u in p.upgrades if u.card_id == pulls[0].card_id]

    cols = st.columns(4)
    cols[0].metric("Total Pulls", len(pulls))
    cols[1].metric("Total Dupes Received", f"{total_dupes:,}")
    cols[2].metric("Total Coins from Card", f"{total_coins:,}")
    cols[3].metric("Upgrades", len(upgrades))

    if upgrades:
        st.markdown("**Upgrade History**")
        upgrade_rows = []
        for u in upgrades:
            upgrade_rows.append(
                {
                    "Day": u.day,
                    "Level": f"{u.old_level} \u2192 {u.new_level}",
                    "Dupes Spent": u.dupes_spent,
                    "Coins Spent": u.coins_spent,
                    "Bluestars": u.bluestars_earned,
                }
            )
        st.dataframe(
            pd.DataFrame(upgrade_rows), use_container_width=True, hide_index=True
        )

    st.markdown("**Pull History**")
    rows = []
    for p in pulls:
        upgrade_str = ""
        card_upgrades = [u for u in p.upgrades if u.card_id == p.card_id]
        if card_upgrades:
            parts = [f"L{u.old_level}\u2192{u.new_level}" for u in card_upgrades]
            upgrade_str = "; ".join(parts)

        rows.append(
            {
                "Day": p.day,
                "Pull#": p.pull_index,
                "Level": p.card_level_before,
                "Dupes": f"+{p.duplicates_received}",
                "Total Dupes": p.duplicates_total_after,
                "Coins": p.coins_earned,
                "Upgrade": upgrade_str,
            }
        )

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
