"""
Main entry point for the Bluestar Economy Simulator.

Provides sidebar navigation between Configuration, Simulation, and Dashboard pages.
Initializes session state with default configuration on first run.
"""

import streamlit as st

from simulation.config_loader import load_defaults

# Must be the first Streamlit command
st.set_page_config(
    page_title="Bluestar Economy Simulator", page_icon="🌌", layout="wide"
)

# Initialize config in session state on first run
if "config" not in st.session_state:
    st.session_state.config = load_defaults()

# Sidebar navigation
st.sidebar.title("🌌 Navigation")
page = st.sidebar.radio(
    "Select a page:",
    ["⚙️ Configuration", "▶️ Simulation", "📊 Dashboard"],
    index=0,
)

# Route to appropriate page
if page == "⚙️ Configuration":
    from pages.config_editor import render_config_editor

    render_config_editor(st.session_state.config)

elif page == "▶️ Simulation":
    st.title("▶️ Simulation")
    st.info("Simulation page coming soon! (Task 13)")

elif page == "📊 Dashboard":
    st.title("📊 Dashboard")
    st.info("Dashboard page coming soon! (Tasks 14-15)")
