"""Config sharing: export, import, save-as-defaults, and diff view."""

import json
from typing import Any, Dict

import streamlit as st

from simulation.config_loader import load_defaults, save_defaults
from simulation.models import SimConfig


def render_config_sharing(config: SimConfig) -> None:
    col_export, col_import = st.columns(2)

    with col_export:
        st.subheader("Export Configuration")
        st.download_button(
            label="Download Config JSON",
            data=config.model_dump_json(indent=2),
            file_name="bluestar_config.json",
            mime="application/json",
            use_container_width=True,
        )

    with col_import:
        st.subheader("Import Configuration")
        uploaded = st.file_uploader(
            "Upload a config JSON file",
            type=["json"],
            key="config_import_uploader",
        )
        if uploaded is not None:
            try:
                content = uploaded.read().decode("utf-8")
                imported = SimConfig.model_validate_json(content)
                st.session_state.config = imported
                st.success("Config imported successfully. Reloading...")
                st.rerun()
            except Exception as e:
                st.error(f"Invalid config file: {e}")

    st.divider()
    _render_save_as_defaults(config)
    st.divider()
    _render_diff_view(config)


def _render_save_as_defaults(config: SimConfig) -> None:
    st.subheader("Save as New Defaults")
    st.caption(
        "Overwrites default JSON files in data/defaults/. Backups are created automatically."
    )

    if "confirm_save_defaults" not in st.session_state:
        st.session_state.confirm_save_defaults = False

    if not st.session_state.confirm_save_defaults:
        if st.button("Save Current Config as Defaults", key="save_defaults_btn"):
            st.session_state.confirm_save_defaults = True
            st.rerun()
    else:
        st.warning("This will overwrite all default configuration files. Are you sure?")
        col_yes, col_no = st.columns(2)
        with col_yes:
            if st.button("Yes, save defaults", type="primary", key="confirm_yes"):
                try:
                    save_defaults(config)
                    st.success(
                        "Defaults saved successfully! Backups created in data/defaults/backups/"
                    )
                except Exception as e:
                    st.error(f"Failed to save defaults: {e}")
                finally:
                    st.session_state.confirm_save_defaults = False
                    st.rerun()
        with col_no:
            if st.button("Cancel", key="confirm_no"):
                st.session_state.confirm_save_defaults = False
                st.rerun()


def _render_diff_view(config: SimConfig) -> None:
    st.subheader("Config vs Defaults")

    if st.button("Compare with Defaults", key="diff_btn"):
        defaults = load_defaults()
        current_dict = json.loads(config.model_dump_json())
        default_dict = json.loads(defaults.model_dump_json())
        diffs = _dict_diff(default_dict, current_dict, prefix="")

        if not diffs:
            st.success("Current config matches defaults exactly.")
        else:
            st.info(f"Found {len(diffs)} difference(s) from defaults.")
            rows = []
            for path, (default_val, current_val) in sorted(diffs.items()):
                rows.append(
                    {
                        "Field": path,
                        "Default": _format_val(default_val),
                        "Current": _format_val(current_val),
                    }
                )
            st.dataframe(rows, use_container_width=True, hide_index=True)


def _dict_diff(d1: Any, d2: Any, prefix: str) -> Dict[str, tuple]:
    diffs: Dict[str, tuple] = {}
    if isinstance(d1, dict) and isinstance(d2, dict):
        all_keys = set(d1.keys()) | set(d2.keys())
        for key in all_keys:
            child_prefix = f"{prefix}.{key}" if prefix else key
            v1 = d1.get(key)
            v2 = d2.get(key)
            if v1 == v2:
                continue
            if isinstance(v1, (dict, list)) and isinstance(v2, (dict, list)):
                diffs.update(_dict_diff(v1, v2, child_prefix))
            else:
                diffs[child_prefix] = (v1, v2)
    elif isinstance(d1, list) and isinstance(d2, list):
        if len(d1) != len(d2):
            diffs[prefix] = (d1, d2)
        else:
            for i, (a, b) in enumerate(zip(d1, d2)):
                if a != b:
                    child_prefix = f"{prefix}[{i}]"
                    if isinstance(a, (dict, list)) and isinstance(b, (dict, list)):
                        diffs.update(_dict_diff(a, b, child_prefix))
                    else:
                        diffs[child_prefix] = (a, b)
    else:
        if d1 != d2:
            diffs[prefix] = (d1, d2)
    return diffs


def _format_val(val: Any) -> str:
    if isinstance(val, (dict, list)):
        s = json.dumps(val)
        return s[:80] + "..." if len(s) > 80 else s
    return str(val)
