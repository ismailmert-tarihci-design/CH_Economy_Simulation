"""Saved results manager for comparing simulation runs."""

from datetime import datetime
from typing import Any, List

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from simulation.config_loader import (
    list_saved_results,
    save_result,
    load_result,
    delete_result,
)
from simulation.models import SavedResult


def render_saved_results_manager() -> None:
    """Render the saved results management and comparison page."""
    st.title("💾 Saved Results")
    st.markdown("Save, load, and compare simulation results.")

    tab_manage, tab_compare = st.tabs(["📂 Manage Results", "📊 Compare Results"])

    with tab_manage:
        _render_manage_tab()

    with tab_compare:
        _render_compare_tab()


def _render_manage_tab() -> None:
    """Render the results management tab."""
    results = list_saved_results()

    if not results:
        st.info(
            "No saved results yet. Run a simulation and save it from the Dashboard."
        )
        return

    st.subheader(f"Saved Results ({len(results)})")

    for result in results:
        with st.container(border=True):
            cols = st.columns([3, 2, 1, 1])

            with cols[0]:
                st.markdown(f"**{result['name']}**")
                if result["description"]:
                    st.caption(result["description"])

            with cols[1]:
                mode_badge = (
                    "🎲 MC" if result["sim_mode"] == "monte_carlo" else "🎯 Det"
                )
                st.markdown(f"{mode_badge} | {result['num_days']} days")
                if result["sim_mode"] == "monte_carlo":
                    st.caption(f"{result['num_runs']} runs")

            with cols[2]:
                st.caption(result["timestamp"][:10])

            with cols[3]:
                col_load, col_del = st.columns(2)
                with col_load:
                    if st.button(
                        "📂", key=f"load_{result['filename']}", help="Load this result"
                    ):
                        loaded = load_result(result["filename"])
                        st.session_state.sim_result = _deserialize_result(loaded)
                        st.session_state.sim_mode = loaded["sim_mode"]
                        loaded_variant = loaded.get("variant_id") or loaded.get(
                            "result", {}
                        ).get("_variant_id")
                        if loaded_variant:
                            st.session_state.active_variant = loaded_variant
                        st.success(f"Loaded '{result['name']}'!")
                with col_del:
                    if st.button("🗑️", key=f"del_{result['filename']}", help="Delete"):
                        delete_result(result["filename"])
                        st.rerun()


def _deserialize_result(loaded: dict) -> Any:
    """Deserialize a saved result back to HeroSimResult / MCResult."""
    from simulation.monte_carlo import MCResult, WelfordAccumulator

    result_data = loaded["result"]

    if loaded["sim_mode"] == "monte_carlo":
        bluestar_stats = WelfordAccumulator()
        bluestar_stats.count = result_data.get("num_runs", 1)
        bluestar_stats.mean = result_data.get("final_bluestar_mean", 0)
        bluestar_stats.m2 = result_data.get("final_bluestar_m2", 0)

        return MCResult(
            num_runs=result_data.get("num_runs", 1),
            bluestar_stats=bluestar_stats,
            daily_bluestar_means=result_data.get("daily_bluestar_means", []),
            daily_bluestar_stds=result_data.get("daily_bluestar_stds", []),
            daily_coin_balance_means=result_data.get("daily_coin_balance_means", []),
            daily_coin_balance_stds=result_data.get("daily_coin_balance_stds", []),
            daily_category_level_means=result_data.get(
                "daily_category_level_means", {}
            ),
            daily_category_level_stds=result_data.get("daily_category_level_stds", {}),
            daily_pull_count_means=result_data.get("daily_pull_count_means", {}),
            daily_pull_count_stds=result_data.get("daily_pull_count_stds", {}),
            daily_pack_count_means=result_data.get("daily_pack_count_means", {}),
            daily_pack_count_stds=result_data.get("daily_pack_count_stds", {}),
            daily_hero_level_means=result_data.get("daily_hero_level_means", {}),
            daily_hero_level_stds=result_data.get("daily_hero_level_stds", {}),
            daily_hero_xp_means=result_data.get("daily_hero_xp_means", {}),
            daily_hero_xp_stds=result_data.get("daily_hero_xp_stds", {}),
            daily_hero_joker_means=result_data.get("daily_hero_joker_means", {}),
            daily_hero_joker_stds=result_data.get("daily_hero_joker_stds", {}),
            daily_hero_total_cards_means=result_data.get("daily_hero_total_cards_means", {}),
            daily_hero_total_cards_stds=result_data.get("daily_hero_total_cards_stds", {}),
            daily_hero_pet_level_means=result_data.get("daily_hero_pet_level_means", {}),
            daily_hero_pet_level_stds=result_data.get("daily_hero_pet_level_stds", {}),
            daily_hero_gear_total_level_means=result_data.get("daily_hero_gear_total_level_means", {}),
            daily_hero_gear_total_level_stds=result_data.get("daily_hero_gear_total_level_stds", {}),
            completion_time=result_data.get("completion_time", 0),
        )

    from simulation.variants.variant_b.models import HeroSimResult
    return HeroSimResult(
        daily_snapshots=result_data.get("daily_snapshots", []),
        total_bluestars=result_data.get("total_bluestars", 0),
        total_coins_earned=result_data.get("total_coins_earned", 0),
        total_coins_spent=result_data.get("total_coins_spent", 0),
        total_upgrades=result_data.get("total_upgrades", {}),
        pull_logs=result_data.get("pull_logs", []),
        final_shared_hero_level=result_data.get("final_shared_hero_level", 0),
        final_shared_hero_xp=result_data.get("final_shared_hero_xp", 0),
        final_hero_levels=result_data.get("final_hero_levels", {}),
        final_hero_xp=result_data.get("final_hero_xp", {}),
        total_premium_diamonds_spent=result_data.get("total_premium_diamonds_spent", 0),
        total_jokers_received=result_data.get("total_jokers_received", 0),
        total_hero_tokens=result_data.get("total_hero_tokens", 0),
        total_hero_tokens_spent=result_data.get("total_hero_tokens_spent", 0),
        final_hero_tokens_balance=result_data.get("final_hero_tokens_balance", 0),
        final_hero_skill_progress=result_data.get("final_hero_skill_progress", {}),
    )


def _render_compare_tab() -> None:
    """Render the results comparison tab."""
    results = list_saved_results()

    if len(results) < 2:
        st.info("Need at least 2 saved results to compare. Save more simulations!")
        return

    st.subheader("Select Results to Compare")

    selected = st.multiselect(
        "Choose 2-4 results to compare",
        options=[r["filename"] for r in results],
        format_func=lambda x: next(r["name"] for r in results if r["filename"] == x),
        max_selections=4,
        key="compare_selection",
    )

    if len(selected) < 2:
        st.info("Select at least 2 results to compare.")
        return

    loaded_results = []
    for filename in selected:
        loaded = load_result(filename)
        loaded_results.append(loaded)

    _render_comparison_metrics(loaded_results)
    _render_comparison_charts(loaded_results)


def _render_comparison_metrics(results: List[dict]) -> None:
    """Render key metrics comparison table."""
    st.subheader("Key Metrics Comparison")

    metrics_data = []
    for r in results:
        result = r["result"]
        metrics_data.append(
            {
                "Name": r["name"],
                "Mode": "MC" if r["sim_mode"] == "monte_carlo" else "Det",
                "Days": r["num_days"],
                "Bluestars": f"{result.get('total_bluestars', 0):,}"
                if r["sim_mode"] == "deterministic"
                else f"{result.get('final_bluestar_mean', 0):.0f} ± {result.get('final_bluestar_std', 0):.0f}",
                "Coins Earned": f"{result.get('total_coins_earned', 0):,}",
                "Upgrades": sum(result.get("total_upgrades", {}).values())
                if r["sim_mode"] == "deterministic"
                else "N/A",
            }
        )

    df = pd.DataFrame(metrics_data)
    st.dataframe(df, hide_index=True, width="stretch")


def _render_comparison_charts(results: List[dict]) -> None:
    """Render comparison charts."""
    st.subheader("Bluestar Progression Comparison")

    fig = go.Figure()

    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]

    for i, r in enumerate(results):
        color = colors[i % len(colors)]
        result = r["result"]
        name = r["name"]

        if r["sim_mode"] == "deterministic":
            snapshots = result.get("daily_snapshots", [])
            days = [s["day"] for s in snapshots]
            bluestars = [s["total_bluestars"] for s in snapshots]

            fig.add_trace(
                go.Scatter(
                    x=days,
                    y=bluestars,
                    mode="lines",
                    name=name,
                    line=dict(color=color, width=2),
                )
            )
        else:
            means = result.get("daily_bluestar_means", [])
            stds = result.get("daily_bluestar_stds", [])
            days = list(range(1, len(means) + 1))

            fig.add_trace(
                go.Scatter(
                    x=days,
                    y=means,
                    mode="lines",
                    name=f"{name} (mean)",
                    line=dict(color=color, width=2),
                )
            )

            upper = [m + s for m, s in zip(means, stds)]
            lower = [m - s for m, s in zip(means, stds)]

            fig.add_trace(
                go.Scatter(
                    x=days + days[::-1],
                    y=upper + lower[::-1],
                    fill="toself",
                    fillcolor=f"rgba{tuple(list(int(color.lstrip('#')[i : i + 2], 16) for i in (0, 2, 4)) + [0.2])}",
                    line=dict(width=0),
                    showlegend=False,
                    hoverinfo="skip",
                )
            )

    fig.update_layout(
        xaxis_title="Day",
        yaxis_title="Total Bluestars",
        hovermode="x unified",
        template="plotly_white",
        height=500,
    )

    st.plotly_chart(fig, width="stretch")


def save_current_result(name: str, description: str = "") -> str:
    """Save the current simulation result from session state."""
    if "sim_result" not in st.session_state:
        raise ValueError("No simulation result to save")

    result = st.session_state.sim_result
    mode = st.session_state.get("sim_mode", "deterministic")
    active = st.session_state.get("active_variant", "variant_b")
    config = st.session_state.get("configs", {}).get(active) or st.session_state.get(
        "config"
    )

    if config is None:
        raise ValueError("No configuration found")

    # Serialize result based on type
    if mode == "monte_carlo":
        mean, std = result.bluestar_stats.result()
        result_data = {
            "num_runs": result.num_runs,
            "final_bluestar_mean": mean,
            "final_bluestar_std": std,
            "final_bluestar_m2": result.bluestar_stats.m2,
            "daily_bluestar_means": result.daily_bluestar_means,
            "daily_bluestar_stds": result.daily_bluestar_stds,
            "daily_coin_balance_means": result.daily_coin_balance_means,
            "daily_coin_balance_stds": result.daily_coin_balance_stds,
            "daily_category_level_means": result.daily_category_level_means,
            "daily_category_level_stds": result.daily_category_level_stds,
            "daily_pull_count_means": result.daily_pull_count_means,
            "daily_pull_count_stds": result.daily_pull_count_stds,
            "daily_pack_count_means": result.daily_pack_count_means,
            "daily_pack_count_stds": result.daily_pack_count_stds,
            "completion_time": result.completion_time,
        }
        # Variant B hero-card MC aggregates (empty dicts on other variants).
        for field_name in (
            "daily_hero_level_means", "daily_hero_level_stds",
            "daily_hero_xp_means", "daily_hero_xp_stds",
            "daily_hero_joker_means", "daily_hero_joker_stds",
            "daily_hero_total_cards_means", "daily_hero_total_cards_stds",
            "daily_hero_pet_level_means", "daily_hero_pet_level_stds",
            "daily_hero_gear_total_level_means", "daily_hero_gear_total_level_stds",
        ):
            if hasattr(result, field_name):
                result_data[field_name] = getattr(result, field_name)
    else:
        from dataclasses import asdict
        result_data = {
            "daily_snapshots": [
                asdict(s) if hasattr(s, "__dataclass_fields__") else s
                for s in result.daily_snapshots
            ],
            "total_bluestars": result.total_bluestars,
            "total_coins_earned": result.total_coins_earned,
            "total_coins_spent": result.total_coins_spent,
            "total_upgrades": _jsonable(result.total_upgrades),
            "pull_logs": [
                asdict(p) if hasattr(p, "__dataclass_fields__") else p
                for p in result.pull_logs
            ],
        }
        # Variant B HeroSimResult aggregates (Pydantic fields beyond the base).
        for field_name in (
            "final_shared_hero_level", "final_shared_hero_xp",
            "final_hero_levels", "final_hero_xp",
            "total_premium_diamonds_spent", "total_jokers_received",
            "total_hero_tokens", "total_hero_tokens_spent",
            "final_hero_tokens_balance", "final_hero_skill_progress",
        ):
            if hasattr(result, field_name):
                result_data[field_name] = getattr(result, field_name)

    result_data["_variant_id"] = active

    saved = SavedResult(
        name=name,
        timestamp=datetime.now().isoformat(),
        description=description,
        sim_mode=mode,
        result=result_data,
        config=config.model_dump(),
        num_days=config.num_days,
        num_runs=result.num_runs if mode == "monte_carlo" else 1,
    )

    payload = saved.model_dump()
    payload["variant_id"] = active
    return save_result(payload)


def _jsonable(obj: Any) -> Any:
    """Best-effort conversion of dataclass / Pydantic / list / dict trees into JSON-safe primitives."""
    from dataclasses import asdict, is_dataclass

    if is_dataclass(obj):
        return asdict(obj)
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    return obj
