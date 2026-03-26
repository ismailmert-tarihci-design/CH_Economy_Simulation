"""Variant A dashboard — Classic Card System.

Re-exports the existing dashboard rendering logic unchanged.
All chart functions remain in dashboard.py and dashboard_charts.py.
"""

from app_pages.dashboard import render_dashboard as _render_full_dashboard


def render_variant_a_dashboard() -> None:
    _render_full_dashboard()
