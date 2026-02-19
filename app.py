"""
Main entry point for the Bluestar Economy Simulator.

Provides sidebar navigation between Configuration, Simulation, and Dashboard pages.
Initializes session state with default configuration on first run.
Supports URL-based config loading via ?cfg=... query parameter.
"""

import streamlit as st

from simulation.config_loader import load_defaults

# Must be the first Streamlit command
st.set_page_config(
    page_title="Bluestar Economy Simulator", page_icon="🌌", layout="wide"
)

if "cfg" in st.query_params:
    if "config_loaded_from_url" not in st.session_state:
        try:
            from simulation.url_config import decode_config

            encoded_config = st.query_params["cfg"]
            decoded = decode_config(encoded_config)
            st.session_state.config = decoded
            st.session_state.config_loaded_from_url = True
            st.success("✅ Configuration loaded from shared URL!")
        except ValueError as e:
            st.error(f"❌ Invalid config URL: {e}")
            if "config" not in st.session_state:
                st.session_state.config = load_defaults()
elif "config" not in st.session_state:
    st.session_state.config = load_defaults()

# Sidebar navigation
st.sidebar.title("🌌 Navigation")
page = st.sidebar.radio(
    "Select a page:",
    ["⚙️ Configuration", "▶️ Simulation", "📊 Dashboard", "📋 Pull Logs"],
    index=0,
)

# Route to appropriate page
if page == "⚙️ Configuration":
    from pages.config_editor import render_config_editor

    render_config_editor(st.session_state.config)

elif page == "▶️ Simulation":
    from pages.simulation_controls import render_simulation_controls

    render_simulation_controls(st.session_state.config)

elif page == "📊 Dashboard":
    from pages.dashboard import render_dashboard

    render_dashboard()

elif page == "📋 Pull Logs":
    from pages.pull_log_viewer import render_pull_log_viewer

    render_pull_log_viewer()
