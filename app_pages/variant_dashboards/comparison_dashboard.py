"""Comparison dashboard — overlay common metrics from two variants."""

import plotly.graph_objects as go
import streamlit as st

from simulation.variants.comparison import extract_common_metrics


VARIANT_COLORS = {
    "variant_a": "#1f77b4",
    "variant_b": "#ff7f0e",
}
VARIANT_LABELS = {
    "variant_a": "Classic Card System",
    "variant_b": "Hero Card System",
}


def render_comparison_dashboard() -> None:
    st.title("Variant Comparison")

    comparison = st.session_state.get("comparison_results")
    if not comparison:
        st.info("No comparison data. Use 'Compare Variants' on the Simulation page.")
        return

    mode = comparison.get("mode", "deterministic")
    variants_data = comparison.get("variants", {})

    if len(variants_data) < 2:
        st.warning("Need results from at least 2 variants to compare.")
        return

    # Extract metrics
    metrics = {}
    for vid, result in variants_data.items():
        metrics[vid] = extract_common_metrics(result, mode)

    # KPI comparison
    _render_kpi_comparison(metrics, mode)
    st.divider()

    # Bluestar overlay
    _render_bluestar_overlay(metrics, mode)

    # Coin overlay
    if mode == "deterministic":
        _render_coin_overlay(metrics)
        _render_category_level_overlay(metrics)


def _render_kpi_comparison(metrics: dict, mode: str) -> None:
    st.subheader("Key Metrics")
    cols = st.columns(len(metrics))
    for i, (vid, m) in enumerate(metrics.items()):
        label = VARIANT_LABELS.get(vid, vid)
        with cols[i]:
            st.markdown(f"**{label}**")
            if mode == "deterministic":
                st.metric("Final Bluestars", f"{m['total_bluestars']:,}")
                st.metric("Coins Earned", f"{m['total_coins_earned']:,}")
            else:
                st.metric("Mean Bluestars", f"{m['total_bluestars_mean']:,.0f}")
                st.metric("MC Runs", m["num_runs"])


def _render_bluestar_overlay(metrics: dict, mode: str) -> None:
    fig = go.Figure()

    for vid, m in metrics.items():
        color = VARIANT_COLORS.get(vid, "#888")
        label = VARIANT_LABELS.get(vid, vid)

        if mode == "deterministic":
            fig.add_trace(go.Scatter(
                x=m["days"], y=m["bluestars"],
                mode="lines", name=label,
                line=dict(color=color, width=2),
            ))
        else:
            means = m["bluestar_means"]
            stds = m["bluestar_stds"]
            days = m["days"]
            upper = [mu + 1.96 * s for mu, s in zip(means, stds)]
            lower = [mu - 1.96 * s for mu, s in zip(means, stds)]
            fig.add_trace(go.Scatter(
                x=days + days[::-1], y=upper + lower[::-1],
                fill="toself", fillcolor=color + "20",
                line=dict(width=0), showlegend=False, hoverinfo="skip",
            ))
            fig.add_trace(go.Scatter(
                x=days, y=means, mode="lines",
                name=f"{label} (mean)", line=dict(color=color, width=2),
            ))

    fig.update_layout(
        title="Bluestar Accumulation — Variant Comparison",
        xaxis=dict(title="Day"), yaxis=dict(title="Total Bluestars"),
        template="plotly_white", hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_coin_overlay(metrics: dict) -> None:
    fig = go.Figure()
    for vid, m in metrics.items():
        color = VARIANT_COLORS.get(vid, "#888")
        label = VARIANT_LABELS.get(vid, vid)
        fig.add_trace(go.Scatter(
            x=m["days"], y=m["coins_balance"],
            mode="lines", name=label,
            line=dict(color=color, width=2),
        ))
    fig.update_layout(
        title="Coin Balance — Variant Comparison",
        xaxis=dict(title="Day"), yaxis=dict(title="Coins"),
        template="plotly_white", hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_category_level_overlay(metrics: dict) -> None:
    # Find shared categories (GOLD_SHARED, BLUE_SHARED exist in both)
    shared_cats = set()
    for m in metrics.values():
        shared_cats.update(m.get("category_avg_levels", {}).keys())
    # Only show categories that appear in ALL variants
    common_cats = None
    for m in metrics.values():
        cats = set(m.get("category_avg_levels", {}).keys())
        common_cats = cats if common_cats is None else common_cats & cats

    if not common_cats:
        return

    fig = go.Figure()
    dash_styles = ["solid", "dash", "dot", "dashdot"]
    for cat_idx, cat in enumerate(sorted(common_cats)):
        for vid_idx, (vid, m) in enumerate(metrics.items()):
            color = VARIANT_COLORS.get(vid, "#888")
            label = VARIANT_LABELS.get(vid, vid)
            levels = m["category_avg_levels"].get(cat, [])
            fig.add_trace(go.Scatter(
                x=m["days"], y=levels,
                mode="lines",
                name=f"{cat} ({label})",
                line=dict(color=color, width=2, dash=dash_styles[cat_idx % len(dash_styles)]),
            ))

    fig.update_layout(
        title="Shared Card Levels — Variant Comparison",
        xaxis=dict(title="Day"), yaxis=dict(title="Avg Card Level"),
        template="plotly_white", hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)
