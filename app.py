"""
Main entry point for the Bluestar Economy Simulator.

Provides navigation between Configuration, Simulation, Dashboard, and tool pages.
Supports A/B variant selection, per-variant config, and URL-based config loading.
"""

import streamlit as st

import simulation.variants as variants

# Must be the first Streamlit command
st.set_page_config(
    page_title="Bluestar Economy Simulator", page_icon="🌌", layout="wide"
)

# --- Variant selector (sidebar, before anything else) ---
with st.sidebar:
    variant_options = {v.variant_id: v.display_name for v in variants.list_variants()}
    active_variant = st.selectbox(
        "Game Variant",
        options=list(variant_options.keys()),
        format_func=lambda x: variant_options[x],
        key="active_variant",
    )

# --- Per-variant config initialization ---
if "configs" not in st.session_state:
    st.session_state.configs = {}

# URL-based config loading (applies to active variant)
if "cfg" in st.query_params:
    if "config_loaded_from_url" not in st.session_state:
        try:
            from simulation.url_config import decode_config

            encoded_config = st.query_params["cfg"]
            decoded = decode_config(encoded_config)
            st.session_state.configs[active_variant] = decoded
            st.session_state.config_loaded_from_url = True
            st.success("Configuration loaded from shared URL!")
        except ValueError as e:
            st.error(f"Invalid config URL: {e}")

# Ensure active variant has a config loaded
if active_variant not in st.session_state.configs:
    variant_info = variants.get(active_variant)
    st.session_state.configs[active_variant] = variant_info.load_defaults()

# Backward compat: st.session_state.config always points to active variant's config
st.session_state.config = st.session_state.configs[active_variant]


# --- Page callables ---
def _page_config():
    from app_pages.config_editor import render_config_editor

    render_config_editor(st.session_state.config, variant_id=active_variant)


def _page_simulation():
    from app_pages.simulation_controls import render_simulation_controls

    render_simulation_controls(st.session_state.config)


def _page_dashboard():
    variant_id = st.session_state.get("active_variant", "variant_a")
    if variant_id == "variant_b":
        from app_pages.variant_dashboards.variant_b_dashboard import (
            render_variant_b_dashboard,
        )

        render_variant_b_dashboard()
    else:
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


# --- Navigation ---
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
                _page_saved_results, title="Saved Results", icon=":material/save:"
            ),
            st.Page(
                _page_pull_logs, title="Pull Logs", icon=":material/list_alt:"
            ),
            st.Page(
                _page_gacha, title="Gacha Simulator", icon=":material/casino:"
            ),
            st.Page(
                _page_docs, title="Documentation", icon=":material/menu_book:"
            ),
        ],
    }
)

# --- Shared sidebar: config sharing ---
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
