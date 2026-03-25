"""
Main entry point for the Bluestar Economy Simulator.

Provides navigation between Configuration, Simulation, Dashboard, and tool pages.
Initializes session state with default configuration on first run.
Supports URL-based config loading via ?cfg=... query parameter.
"""

import streamlit as st

from simulation.config_loader import load_defaults

# Must be the first Streamlit command
st.set_page_config(
    page_title="Bluestar Economy Simulator", page_icon="🌌", layout="wide"
)

# URL-based config loading
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


# Page callables (thin wrappers so st.navigation can invoke them)
def _page_config():
    from app_pages.config_editor import render_config_editor

    render_config_editor(st.session_state.config)


def _page_simulation():
    from app_pages.simulation_controls import render_simulation_controls

    render_simulation_controls(st.session_state.config)


def _page_dashboard():
    from app_pages.dashboard import render_dashboard

    render_dashboard()


def _page_saved_results():
    from app_pages.results_manager import render_saved_results_manager

    render_saved_results_manager()


def _page_pull_logs():
    from app_pages.pull_log_viewer import render_pull_log_viewer

    render_pull_log_viewer()


def _page_gacha():
    from app_pages.gacha_simulator import render_gacha_simulator

    render_gacha_simulator()


def _page_docs():
    from app_pages.documentation import render_documentation

    render_documentation()


# Navigation
page = st.navigation(
    {
        "Simulation": [
            st.Page(_page_config, title="Configuration", icon=":material/settings:"),
            st.Page(
                _page_simulation, title="Simulation", icon=":material/play_arrow:"
            ),
            st.Page(_page_dashboard, title="Dashboard", icon=":material/bar_chart:"),
        ],
        "Tools": [
            st.Page(
                _page_saved_results,
                title="Saved Results",
                icon=":material/save:",
            ),
            st.Page(
                _page_pull_logs, title="Pull Logs", icon=":material/list_alt:"
            ),
            st.Page(
                _page_gacha,
                title="Gacha Simulator",
                icon=":material/casino:",
            ),
            st.Page(
                _page_docs, title="Documentation", icon=":material/menu_book:"
            ),
        ],
    }
)

# Shared sidebar: config sharing
with st.sidebar:
    st.divider()
    st.caption("Share Configuration")
    if st.button("Copy Shareable URL", use_container_width=True):
        try:
            from simulation.url_config import encode_config

            encoded = encode_config(st.session_state.config)
            base_url = st.context.headers.get("host", "localhost:8501")
            protocol = "https" if "streamlit.app" in base_url else "http"
            share_url = f"{protocol}://{base_url}/?cfg={encoded}"
            st.code(share_url, language="text")
        except Exception as e:
            st.error(f"Failed: {e}")

page.run()
