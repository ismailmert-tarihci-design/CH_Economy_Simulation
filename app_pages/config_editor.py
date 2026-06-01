"""Config editor page — dispatches to the active variant's editor."""

import streamlit as st


def render_config_editor(config, variant_id: str = "variant_b") -> None:
    st.title("Configuration")

    from app_pages.variant_editors.variant_b_editor import render_variant_b_editor

    render_variant_b_editor(config)
