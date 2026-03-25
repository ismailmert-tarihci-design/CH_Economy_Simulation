"""
Simulation controls page for the Bluestar Economy Simulator.

Provides simulation parameter inputs, run buttons for deterministic and Monte Carlo modes,
progress tracking, and URL-based configuration sharing for team collaboration.
"""

import hashlib
from typing import Any

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

    st.subheader("🎯 Goal-Based Simulation")
    use_goal_mode = st.toggle(
        "Enable Goal Mode",
        value=False,
        help="Set a target outcome and instantly see whether your current setup reaches it.",
    )

    goal_settings: dict[str, Any] = {}
    if use_goal_mode:
        available_goals = [
            "Bluestars by Day",
            "Hero Unique Pool by Day",
            "Pet Tier by Day",
            "Average Gear Level by Day",
        ]
        if mode == "Monte Carlo":
            available_goals = ["Bluestars by Day"]
            st.info(
                "In Monte Carlo mode, goal checks are currently available for bluestars only. "
                "Switch to deterministic for hero/pet/gear goal checks."
            )

        col_goal_1, col_goal_2, col_goal_3 = st.columns(3)
        with col_goal_1:
            goal_type = st.selectbox("Goal", available_goals, key="goal_type")
        with col_goal_2:
            goal_day = st.number_input(
                "Target Day",
                min_value=1,
                max_value=730,
                value=min(30, int(num_days)),
                step=1,
                key="goal_day",
            )
        with col_goal_3:
            if goal_type == "Bluestars by Day":
                goal_value = st.number_input(
                    "Target Bluestars",
                    min_value=0,
                    value=500,
                    step=50,
                    key="goal_value_bluestars",
                )
            elif goal_type == "Hero Unique Pool by Day":
                goal_value = st.number_input(
                    "Target Unique Pool",
                    min_value=0,
                    value=10,
                    step=1,
                    key="goal_value_hero_pool",
                )
            elif goal_type == "Pet Tier by Day":
                goal_value = st.number_input(
                    "Target Pet Tier",
                    min_value=1,
                    max_value=15,
                    value=3,
                    step=1,
                    key="goal_value_pet_tier",
                )
            else:
                goal_value = st.number_input(
                    "Target Avg Gear Level",
                    min_value=1.0,
                    max_value=100.0,
                    value=10.0,
                    step=0.5,
                    key="goal_value_gear_level",
                )

        goal_settings = {
            "goal_type": goal_type,
            "goal_day": int(goal_day),
            "goal_value": float(goal_value),
        }

    if st.button("▶️ Run Simulation", type="primary", use_container_width=True):
        config.num_days = num_days
        config_hash = hashlib.md5(config.model_dump_json().encode()).hexdigest()

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

        if use_goal_mode and goal_settings:
            achieved, summary = _evaluate_goal(
                result=result,
                sim_mode=st.session_state.sim_mode,
                goal_type=str(goal_settings["goal_type"]),
                goal_day=int(goal_settings["goal_day"]),
                goal_value=float(goal_settings["goal_value"]),
            )
            if achieved:
                st.success(f"🎯 Goal Reached: {summary}")
            else:
                st.warning(f"🎯 Goal Not Reached: {summary}")

        st.info("📊 View results in the Dashboard page.")

    st.divider()
    st.subheader("📋 Share Configuration")
    st.caption("Generate a shareable URL containing your current configuration")

    if st.button("Generate Shareable URL", use_container_width=True):
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
def _run_cached_simulation(config_hash: str, _config: SimConfig):
    """
    Run and cache deterministic simulation.

    Args:
        config_hash: MD5 hash of config JSON for cache key
        _config: SimConfig object (underscore prefix = don't hash)

    Returns:
        SimResult from run_simulation
    """
    _ = config_hash
    return run_simulation(_config, rng=None)


@st.cache_data(ttl=3600, max_entries=10)
def _run_cached_mc(config_hash: str, _config: SimConfig, num_runs: int):
    """
    Run and cache Monte Carlo simulation.

    Args:
        config_hash: MD5 hash of config JSON for cache key
        _config: SimConfig object (underscore prefix = don't hash)
        num_runs: Number of Monte Carlo runs

    Returns:
        MCResult from run_monte_carlo
    """
    _ = config_hash
    return run_monte_carlo(_config, num_runs=num_runs)


def _evaluate_goal(
    result: Any,
    sim_mode: str,
    goal_type: str,
    goal_day: int,
    goal_value: float,
) -> tuple[bool, str]:
    if goal_type == "Bluestars by Day":
        if sim_mode == "deterministic":
            snapshots = result.daily_snapshots
            day_index = min(goal_day, len(snapshots)) - 1
            actual = float(snapshots[day_index].total_bluestars)
        else:
            day_index = min(goal_day, len(result.daily_bluestar_means)) - 1
            actual = float(result.daily_bluestar_means[day_index])
        achieved = actual >= goal_value
        gap = actual - goal_value
        return achieved, (
            f"Day {goal_day}: {actual:.1f} bluestars vs target {goal_value:.1f} "
            f"(gap {gap:+.1f})"
        )

    if sim_mode != "deterministic":
        return False, "This goal is supported in deterministic mode only."

    snapshots = result.daily_snapshots
    upto = snapshots[: max(1, min(goal_day, len(snapshots)))]

    if goal_type == "Hero Unique Pool by Day":
        actual = 0.0
        for snapshot in upto:
            for event in snapshot.hero_unlock_events:
                actual = max(actual, float(event.get("total_unique_pool_after", 0)))
        achieved = actual >= goal_value
        gap = actual - goal_value
        return achieved, (
            f"Day {goal_day}: unique pool {actual:.1f} vs target {goal_value:.1f} "
            f"(gap {gap:+.1f})"
        )

    if goal_type == "Pet Tier by Day":
        actual = 1.0
        for snapshot in upto:
            for event in snapshot.pet_events:
                actual = max(actual, float(event.get("tier_after", 1)))
        achieved = actual >= goal_value
        gap = actual - goal_value
        return achieved, (
            f"Day {goal_day}: pet tier {actual:.0f} vs target {goal_value:.0f} "
            f"(gap {gap:+.0f})"
        )

    if goal_type == "Average Gear Level by Day":
        slot_levels = {slot_id: 1 for slot_id in range(1, 7)}
        for snapshot in upto:
            for event in snapshot.gear_events:
                slot_id = int(event.get("slot_id", 0))
                if 1 <= slot_id <= 6:
                    slot_levels[slot_id] = max(
                        slot_levels[slot_id], int(event.get("new_level", 1))
                    )
        actual = float(sum(slot_levels.values()) / 6.0)
        achieved = actual >= goal_value
        gap = actual - goal_value
        return achieved, (
            f"Day {goal_day}: avg gear level {actual:.2f} vs target {goal_value:.2f} "
            f"(gap {gap:+.2f})"
        )

    return False, "Unknown goal type."
