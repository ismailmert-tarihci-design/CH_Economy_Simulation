"""Config editor page — dispatches to the active variant's editor."""

import streamlit as st


def render_config_editor(config, variant_id: str = "variant_a") -> None:
    st.title("Configuration")

    if variant_id == "variant_a":
        from app_pages.variant_editors.variant_a_editor import render_variant_a_editor

        render_variant_a_editor(config)
    elif variant_id == "variant_b":
        from app_pages.variant_editors.variant_b_editor import render_variant_b_editor

        render_variant_b_editor(config)
    else:
        st.error(f"Unknown variant: {variant_id}")
