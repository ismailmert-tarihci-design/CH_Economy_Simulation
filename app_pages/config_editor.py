import streamlit as st

from app_pages.config_sharing import render_config_sharing
from app_pages.config_tabs import (
    render_pack_config,
    render_upgrade_tables,
    render_card_economy,
    render_progression_schedule,
    render_drop_algorithm,
    render_pet_hero_gear,
    render_profiles,
)
from simulation.models import SimConfig


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

    col_gold, col_blue = st.columns(2)
    with col_gold:
        config.num_gold_cards = st.number_input(
            "Gold Shared Cards",
            min_value=1,
            max_value=50,
            value=config.num_gold_cards,
            step=1,
            key="num_gold_cards",
        )
    with col_blue:
        config.num_blue_cards = st.number_input(
            "Blue Shared Cards",
            min_value=1,
            max_value=50,
            value=config.num_blue_cards,
            step=1,
            key="num_blue_cards",
        )

    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(
        [
            "📦 Pack Configuration",
            "⬆️ Upgrade Tables",
            "💰 Card Economy",
            "📈 Progression & Schedule",
            "🎲 Drop Algorithm",
            "🐾 Pet/Hero/Gear",
            "👤 Profiles",
            "📤 Import / Export",
        ]
    )

    with tab1:
        render_pack_config(config)
    with tab2:
        render_upgrade_tables(config)
    with tab3:
        render_card_economy(config)
    with tab4:
        render_progression_schedule(config)
    with tab5:
        render_drop_algorithm(config)
    with tab6:
        render_pet_hero_gear(config)
    with tab7:
        render_profiles(config)
    with tab8:
        render_config_sharing(config)
