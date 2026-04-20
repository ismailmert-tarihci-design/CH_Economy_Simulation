"""Comparison dashboard — overlay common metrics from two variants."""

import pandas as pd
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

    # KPI comparison table
    _render_kpi_comparison(metrics, mode)
    st.divider()

    # Bluestar overlay
    _render_bluestar_overlay(metrics, mode)

    if mode == "deterministic":
        # Daily bluestar rate
        _render_daily_bluestar_rate(metrics)

        # Coin overlay (earned + spent)
        _render_coin_overlay(metrics)

        # Daily coin rates
        _render_daily_coin_rates(metrics)

        # Category level overlay
        _render_category_level_overlay(metrics)


def _render_kpi_comparison(metrics: dict, mode: str) -> None:
    st.subheader("Key Metrics")

    if mode == "deterministic":
        rows = []
        for metric_name, key, fmt in [
            ("Total Bluestars", "total_bluestars", "{:,}"),
            ("Total Coins Earned", "total_coins_earned", "{:,}"),
            ("Total Coins Spent", "total_coins_spent", "{:,}"),
            ("Net Coin Balance", None, "{:,}"),
            ("Total Upgrades", "total_upgrades", "{:,}"),
            ("Total Pulls", None, "{:,}"),
            ("Avg Bluestars/Day", None, "{:,.1f}"),
        ]:
            row = {"Metric": metric_name}
            for vid, m in metrics.items():
                label = VARIANT_LABELS.get(vid, vid)
                if key:
                    row[label] = fmt.format(m.get(key, 0))
                elif metric_name == "Net Coin Balance":
                    row[label] = fmt.format(m.get("total_coins_earned", 0) - m.get("total_coins_spent", 0))
                elif metric_name == "Total Pulls":
                    row[label] = fmt.format(sum(m.get("pull_counts_daily", [])))
                elif metric_name == "Avg Bluestars/Day":
                    days = m.get("days", [])
                    bs = m.get("total_bluestars", 0)
                    row[label] = fmt.format(bs / len(days)) if days else "N/A"
            rows.append(row)

        df = pd.DataFrame(rows)
        st.dataframe(df, width="stretch", hide_index=True)
    else:
        cols = st.columns(len(metrics))
        for i, (vid, m) in enumerate(metrics.items()):
            label = VARIANT_LABELS.get(vid, vid)
            with cols[i]:
                st.markdown(f"**{label}**")
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
        title="Bluestar Accumulation",
        xaxis=dict(title="Day"), yaxis=dict(title="Total Bluestars"),
        template="plotly_white", hovermode="x unified",
    )
    st.plotly_chart(fig, width="stretch")


def _render_daily_bluestar_rate(metrics: dict) -> None:
    fig = go.Figure()
    for vid, m in metrics.items():
        color = VARIANT_COLORS.get(vid, "#888")
        label = VARIANT_LABELS.get(vid, vid)
        daily = m.get("bluestars_daily", [])
        if daily:
            fig.add_trace(go.Scatter(
                x=m["days"], y=daily,
                mode="lines", name=label,
                line=dict(color=color, width=2),
            ))
    fig.update_layout(
        title="Daily Bluestar Income",
        xaxis=dict(title="Day"), yaxis=dict(title="Bluestars Earned"),
        template="plotly_white", hovermode="x unified",
    )
    st.plotly_chart(fig, width="stretch")


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
        title="Coin Balance",
        xaxis=dict(title="Day"), yaxis=dict(title="Coins"),
        template="plotly_white", hovermode="x unified",
    )
    st.plotly_chart(fig, width="stretch")


def _render_daily_coin_rates(metrics: dict) -> None:
    fig = go.Figure()
    dash_map = {"variant_a": "solid", "variant_b": "dash"}
    for vid, m in metrics.items():
        color = VARIANT_COLORS.get(vid, "#888")
        label = VARIANT_LABELS.get(vid, vid)
        dash = dash_map.get(vid, "solid")

        earned = m.get("coins_earned_daily", [])
        spent = m.get("coins_spent_daily", [])
        if earned:
            fig.add_trace(go.Scatter(
                x=m["days"], y=earned,
                mode="lines", name=f"{label} — Earned",
                line=dict(color=color, width=2, dash=dash),
            ))
        if spent:
            fig.add_trace(go.Scatter(
                x=m["days"], y=spent,
                mode="lines", name=f"{label} — Spent",
                line=dict(color=color, width=1.5, dash="dot"),
            ))

    fig.update_layout(
        title="Daily Coin Income vs Spending",
        xaxis=dict(title="Day"), yaxis=dict(title="Coins"),
        template="plotly_white", hovermode="x unified",
    )
    st.plotly_chart(fig, width="stretch")


def _render_category_level_overlay(metrics: dict) -> None:
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
        for vid, m in metrics.items():
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
        title="Shared Card Levels",
        xaxis=dict(title="Day"), yaxis=dict(title="Avg Card Level"),
        template="plotly_white", hovermode="x unified",
    )
    st.plotly_chart(fig, width="stretch")
