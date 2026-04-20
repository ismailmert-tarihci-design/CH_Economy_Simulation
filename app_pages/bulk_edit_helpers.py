"""Bulk edit helpers for config tables.

Provides Excel/CSV upload, download, and paste-from-clipboard utilities
to make editing large config tables faster. Works with any st.data_editor.
"""

import io
from typing import Optional

import pandas as pd
import streamlit as st


def render_bulk_edit_bar(
    table_key: str,
    current_df: pd.DataFrame,
    label: str = "table",
) -> Optional[pd.DataFrame]:
    """Render upload/download/paste controls above a data editor.

    Call this BEFORE the st.data_editor. If it returns a DataFrame,
    use that instead of the current one (user uploaded/pasted new data).

    Args:
        table_key: Unique key prefix for widgets
        current_df: The current DataFrame being edited
        label: Human-readable table name for UI labels

    Returns:
        Replacement DataFrame if user uploaded/pasted, else None
    """
    replacement_df = None

    # Paste area always visible for quick Google Sheets workflow
    pasted = st.text_area(
        f"Paste from Google Sheets / Excel ({label})",
        height=68,
        key=f"bulk_paste_{table_key}",
        placeholder="Paste tab-separated rows here. Include headers, or omit them to match by column position.",
    )
    if pasted and pasted.strip():
        try:
            replacement_df = _parse_pasted_data(pasted, current_df)
            st.success(f"Parsed {len(replacement_df)} rows from pasted data")
        except Exception as e:
            st.error(f"Failed to parse pasted data: {e}")

    # Download and upload in a compact row
    col_dl, col_ul = st.columns(2)
    with col_dl:
        csv_data = current_df.to_csv(index=False)
        st.download_button(
            "Download CSV",
            data=csv_data,
            file_name=f"{table_key}.csv",
            mime="text/csv",
            width="stretch",
            key=f"bulk_dl_{table_key}",
        )
    with col_ul:
        uploaded = st.file_uploader(
            "Upload CSV/Excel",
            type=["csv", "xlsx", "xls"],
            key=f"bulk_ul_{table_key}",
            label_visibility="collapsed",
        )
        if uploaded is not None:
            try:
                if uploaded.name.endswith((".xlsx", ".xls")):
                    replacement_df = pd.read_excel(uploaded)
                else:
                    replacement_df = pd.read_csv(uploaded)
                st.success(f"Loaded {len(replacement_df)} rows from {uploaded.name}")
            except Exception as e:
                st.error(f"Failed to parse file: {e}")

    return replacement_df


def _parse_pasted_data(pasted: str, current_df: pd.DataFrame) -> pd.DataFrame:
    """Parse tab-separated paste. Auto-detect whether headers are present."""
    df = pd.read_csv(io.StringIO(pasted), sep="\t")

    # If the parsed header looks like data (first column header is numeric or
    # doesn't match any expected column), treat the first row as data too
    expected_cols = set(current_df.columns)
    parsed_cols = set(df.columns)

    if not (parsed_cols & expected_cols):
        # No header match — re-parse without headers and map by position
        df = pd.read_csv(io.StringIO(pasted), sep="\t", header=None)
        if len(df.columns) == len(current_df.columns):
            df.columns = current_df.columns
        else:
            # Column count mismatch — fall back to raw parse with generated headers
            df = pd.read_csv(io.StringIO(pasted), sep="\t")

    return df
