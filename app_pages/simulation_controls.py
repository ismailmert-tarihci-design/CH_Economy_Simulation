"""
Simulation controls — run deterministic or Monte Carlo simulations,
set goals, compare variants, and share configurations.
"""

import hashlib
from typing import Any

import streamlit as st

import simulation.variants as variants
from simulation.monte_carlo import run_monte_carlo
from simulation.url_config import encode_config


def render_simulation_controls(config: Any) -> None:
    st.title("Run simulation")

    # ─── Mode & duration ──────────────────────────────────────────────────────
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            num_days = st.number_input(
                "Simulation days",
                min_value=1,
                max_value=730,
                value=100,
                step=1,
            )
        with col2:
            mode = st.segmented_control(
                "Mode",
                ["Deterministic", "Monte Carlo"],
                default="Deterministic",
            )
            if mode is None:
                mode = "Deterministic"

        num_runs = 100
        if mode == "Monte Carlo":
            num_runs = st.number_input(
                "Monte Carlo runs",
                min_value=10,
                max_value=500,
                value=100,
                step=10,
            )
            if num_runs > 200:
                st.caption(":material/info: More than 200 runs may be slow. Consider 100 for quick results.")
            if num_days > 365:
                st.caption(":material/info: MC mode capped at 365 days for performance.")
                num_days = 365

    # ─── Goal mode ────────────────────────────────────────────────────────────
    goal_settings: dict[str, Any] = {}
    with st.expander("Goal-based simulation", icon=":material/target:"):
        use_goal_mode = st.toggle("Enable goal mode")

        if use_goal_mode:
            available_goals = [
                "Bluestars by Day",
                "Hero Unique Pool by Day",
                "Pet Tier by Day",
                "Average Gear Level by Day",
            ]
            if mode == "Monte Carlo":
                available_goals = ["Bluestars by Day"]
                st.caption("MC mode: only bluestar goals are currently supported.")

            col_goal_1, col_goal_2, col_goal_3 = st.columns(3)
            with col_goal_1:
                goal_type = st.selectbox("Goal", available_goals, key="goal_type")
            with col_goal_2:
                goal_day = st.number_input(
                    "Target day",
                    min_value=1,
                    max_value=730,
                    value=min(30, int(num_days)),
                    step=1,
                    key="goal_day",
                )
            with col_goal_3:
                if goal_type == "Bluestars by Day":
                    goal_value = st.number_input("Target bluestars", min_value=0, value=500, step=50, key="goal_value_bluestars")
                elif goal_type == "Hero Unique Pool by Day":
                    goal_value = st.number_input("Target unique pool", min_value=0, value=10, step=1, key="goal_value_hero_pool")
                elif goal_type == "Pet Tier by Day":
                    goal_value = st.number_input("Target pet tier", min_value=1, max_value=15, value=3, step=1, key="goal_value_pet_tier")
                else:
                    goal_value = st.number_input("Target avg gear level", min_value=1.0, max_value=100.0, value=10.0, step=0.5, key="goal_value_gear_level")

            goal_settings = {
                "goal_type": goal_type,
                "goal_day": int(goal_day),
                "goal_value": float(goal_value),
            }

    # ─── Run button ───────────────────────────────────────────────────────────
    variant_id = st.session_state.get("active_variant", "variant_a")

    if st.button("Run simulation", type="primary", use_container_width=True, icon=":material/play_arrow:"):
        config.num_days = num_days
        config_hash = hashlib.md5(config.model_dump_json().encode()).hexdigest()

        if mode == "Deterministic":
            with st.spinner("Running deterministic simulation..."):
                result = _run_cached_simulation(config_hash, config, variant_id)
            st.session_state.sim_result = result
            st.session_state.sim_mode = "deterministic"
            st.success(
                f"Complete — final bluestars: {result.total_bluestars}",
                icon=":material/check_circle:",
            )
        else:
            with st.spinner(f"Running {num_runs} Monte Carlo trials..."):
                result = _run_cached_mc(config_hash, config, num_runs, variant_id)
            st.session_state.sim_result = result
            st.session_state.sim_mode = "monte_carlo"
            mean, std = result.bluestar_stats.result()
            st.success(
                f"Complete — bluestars: {mean:.1f} +/- {std:.1f} ({num_runs} runs, {result.completion_time:.1f}s)",
                icon=":material/check_circle:",
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
                st.success(f"Goal reached: {summary}", icon=":material/target:")
            else:
                st.warning(f"Goal not reached: {summary}", icon=":material/target:")

        st.caption("View results in the **Dashboard** page.")

    # ─── Compare variants ─────────────────────────────────────────────────────
    if len(variants.list_variants()) > 1:
        with st.expander("Compare variants", icon=":material/compare_arrows:"):
            st.caption("Run both variants with the same day count and compare side-by-side.")

            if st.button("Compare all variants (deterministic)", use_container_width=True, icon=":material/compare_arrows:"):
                config.num_days = num_days
                comparison_results = {"mode": "deterministic", "variants": {}}
                for v in variants.list_variants():
                    v_config = st.session_state.configs.get(v.variant_id)
                    if v_config is None:
                        v_config = v.load_defaults()
                    v_config.num_days = num_days
                    with st.spinner(f"Running {v.display_name}..."):
                        result = v.run_simulation(v_config, rng=None)
                    comparison_results["variants"][v.variant_id] = result
                st.session_state.comparison_results = comparison_results
                st.success("Comparison complete. Switch to Dashboard to view.", icon=":material/check_circle:")

    # ─── Share config ─────────────────────────────────────────────────────────
    with st.expander("Share configuration", icon=":material/share:"):
        st.caption("Generate a URL containing your current configuration for team sharing.")
        if st.button("Generate shareable URL", use_container_width=True, icon=":material/link:"):
            try:
                encoded = encode_config(config)
                base_url = st.context.headers.get("host", "localhost:8501")
                protocol = "https" if "streamlit.app" in base_url else "http"
                share_url = f"{protocol}://{base_url}/?cfg={encoded}"
                st.code(share_url, language="text")
                st.caption("Copy and share. Recipients will load your exact configuration.")
            except Exception as e:
                st.error(f"Failed to generate URL: {e}")


@st.cache_data(ttl=3600, max_entries=10)
def _run_cached_simulation(config_hash: str, _config: Any, variant_id: str = "variant_a"):
    _ = config_hash
    run_fn = variants.get(variant_id).run_simulation
    return run_fn(_config, rng=None)


@st.cache_data(ttl=3600, max_entries=10)
def _run_cached_mc(config_hash: str, _config: Any, num_runs: int, variant_id: str = "variant_a"):
    _ = config_hash
    run_fn = variants.get(variant_id).run_simulation
    return run_monte_carlo(_config, num_runs=num_runs, run_fn=run_fn)


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
        return achieved, f"Day {goal_day}: {actual:.1f} bluestars vs target {goal_value:.1f} (gap {gap:+.1f})"

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
        return achieved, f"Day {goal_day}: unique pool {actual:.1f} vs target {goal_value:.1f} (gap {gap:+.1f})"

    if goal_type == "Pet Tier by Day":
        actual = 1.0
        for snapshot in upto:
            for event in snapshot.pet_events:
                actual = max(actual, float(event.get("tier_after", 1)))
        achieved = actual >= goal_value
        gap = actual - goal_value
        return achieved, f"Day {goal_day}: pet tier {actual:.0f} vs target {goal_value:.0f} (gap {gap:+.0f})"

    if goal_type == "Average Gear Level by Day":
        slot_levels = {slot_id: 1 for slot_id in range(1, 7)}
        for snapshot in upto:
            for event in snapshot.gear_events:
                slot_id = int(event.get("slot_id", 0))
                if 1 <= slot_id <= 6:
                    slot_levels[slot_id] = max(slot_levels[slot_id], int(event.get("new_level", 1)))
        actual = float(sum(slot_levels.values()) / 6.0)
        achieved = actual >= goal_value
        gap = actual - goal_value
        return achieved, f"Day {goal_day}: avg gear level {actual:.2f} vs target {goal_value:.2f} (gap {gap:+.2f})"

    return False, "Unknown goal type."
