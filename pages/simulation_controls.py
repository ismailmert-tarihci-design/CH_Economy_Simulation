"""
Simulation controls page for the Bluestar Economy Simulator.

Provides simulation parameter inputs, run buttons for deterministic and Monte Carlo modes,
progress tracking, and URL-based configuration sharing for team collaboration.
"""

import hashlib

import streamlit as st

from simulation.models import SimConfig
from simulation.monte_carlo import run_monte_carlo
from simulation.orchestrator import run_simulation
from simulation.url_config import encode_config


def render_simulation_controls(config: SimConfig) -> None:
    """
    Render simulation control interface.

    Args:
        config: Current SimConfig from session state
    """
    st.title("▶️ Simulation Controls")
    st.markdown("Configure and run simulations. Results are cached for performance.")

    col1, col2 = st.columns(2)

    with col1:
        num_days = st.number_input(
            "Number of Days",
            min_value=1,
            max_value=730,
            value=100,
            step=1,
            help="Simulation duration (1-730 days)",
        )

    with col2:
        mode = st.radio(
            "Simulation Mode",
            ["Deterministic", "Monte Carlo"],
            help="Deterministic: single run with fixed seed. Monte Carlo: statistical analysis.",
        )

    num_runs = 100
    if mode == "Monte Carlo":
        num_runs = st.number_input(
            "Number of Monte Carlo Runs",
            min_value=10,
            max_value=500,
            value=100,
            step=10,
            help="Number of simulation runs for statistical analysis",
        )

        if num_runs > 200:
            st.warning(
                "⚠️ More than 200 runs may be slow. Consider 100 runs for quick results."
            )

        if num_days > 365:
            st.info(
                "ℹ️ Monte Carlo mode limited to 365 days for performance. Adjusting to 365 days."
            )
            num_days = 365

    st.divider()

    if st.button("▶️ Run Simulation", type="primary", width="stretch"):
        config.num_days = num_days
        config_hash = hashlib.md5(config.model_dump_json().encode()).hexdigest()

        # Clear cache to ensure fresh results with updated config
        _run_cached_simulation.clear()
        _run_cached_mc.clear()

        if mode == "Deterministic":
            with st.spinner("Running deterministic simulation..."):
                result = _run_cached_simulation(config_hash, config)
            st.session_state.sim_result = result
            st.session_state.sim_mode = "deterministic"
            st.success(
                f"✅ Deterministic simulation complete! "
                f"Final bluestars: {result.total_bluestars}"
            )
        else:
            with st.spinner(f"Running {num_runs} Monte Carlo trials..."):
                result = _run_cached_mc(config_hash, config, num_runs)
            st.session_state.sim_result = result
            st.session_state.sim_mode = "monte_carlo"
            mean, std = result.bluestar_stats.result()
            st.success(
                f"✅ Monte Carlo simulation complete! Final bluestars: {mean:.1f} ± {std:.1f} ({num_runs} runs in {result.completion_time:.1f}s)"
            )

        st.info("📊 View results in the Dashboard page.")

    st.divider()
    st.subheader("📋 Share Configuration")
    st.caption("Generate a shareable URL containing your current configuration")

    if st.button("Generate Shareable URL", width="stretch"):
        try:
            encoded = encode_config(config)
            base_url = st.context.headers.get("host", "localhost:8501")
            protocol = "https" if "streamlit.app" in base_url else "http"
            share_url = f"{protocol}://{base_url}/?cfg={encoded}"

            st.code(share_url, language="text")
            st.success(
                "✅ URL generated! Copy and share with your team. Recipients will load your exact configuration."
            )
        except Exception as e:
            st.error(f"❌ Failed to generate URL: {e}")


@st.cache_data(ttl=3600, max_entries=10)
def _run_cached_simulation(_config_hash: str, _config: SimConfig):
    """
    Run and cache deterministic simulation.

    Args:
        _config_hash: MD5 hash of config JSON for cache key
        _config: SimConfig object (underscore prefix = don't hash)

    Returns:
        SimResult from run_simulation
    """
    return run_simulation(_config, rng=None)


@st.cache_data(ttl=3600, max_entries=10)
def _run_cached_mc(_config_hash: str, _config: SimConfig, num_runs: int):
    """
    Run and cache Monte Carlo simulation.

    Args:
        _config_hash: MD5 hash of config JSON for cache key
        _config: SimConfig object (underscore prefix = don't hash)
        num_runs: Number of Monte Carlo runs

    Returns:
        MCResult from run_monte_carlo
    """
    return run_monte_carlo(_config, num_runs=num_runs)
