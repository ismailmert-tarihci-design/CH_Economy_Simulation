"""Tests for the day-sim settings persistence and the post-pass infinite
pack + season-cycle helpers (Variant B)."""

from __future__ import annotations

from random import Random

import pytest

from simulation.variants.variant_b import day_sim_settings as dss
from simulation.variants.variant_b import season_pass as sp
from simulation.variants.variant_b.config_loader import load_defaults
from simulation.variants.variant_b.day_simulator import init_state


# ─── Settings persistence + resolvers ────────────────────────────────────────

def test_settings_roundtrip(tmp_path, monkeypatch):
    path = tmp_path / "day_sim_settings.json"
    monkeypatch.setattr(dss, "_settings_path", lambda: path)

    # Missing file → defaults.
    s = dss.load_day_sim_settings()
    assert s.cohort == "Average"
    assert s.season_length_days == 28

    s.cohort = "P90"
    s.bs_gating = "Payer"
    s.paid_pass = True
    s.season_length_days = 14
    s.chapters_per_day_overrides["P90"] = [0, 5, 5]
    s.bluestar_threshold_overrides["Payer"] = [0.0, 10.0, 99.0]
    dss.save_day_sim_settings(s)

    loaded = dss.load_day_sim_settings()
    assert loaded.cohort == "P90"
    assert loaded.bs_gating == "Payer"
    assert loaded.paid_pass is True
    assert loaded.season_length_days == 14
    assert loaded.chapters_per_day_overrides["P90"] == [0, 5, 5]
    assert loaded.bluestar_threshold_overrides["Payer"] == [0.0, 10.0, 99.0]


def test_load_invalid_file_returns_defaults(tmp_path, monkeypatch):
    path = tmp_path / "day_sim_settings.json"
    path.write_text("{ not valid json", encoding="utf-8")
    monkeypatch.setattr(dss, "_settings_path", lambda: path)
    assert dss.load_day_sim_settings().cohort == "Average"


def test_effective_chapters_override_wins():
    s = dss.DaySimSettings(chapters_per_day_overrides={"Average": [9, 9, 9]})
    assert dss.effective_chapters_per_day(s, "Average") == [9, 9, 9]
    # No override → falls back to the shipped profile (non-empty for Average).
    assert dss.effective_chapters_per_day(s, "P75")


def test_effective_thresholds_override_and_calendar():
    s = dss.DaySimSettings(bluestar_threshold_overrides={"Payer": [0.0, 5.0]})
    assert dss.effective_bluestar_thresholds(s, "Payer") == [0.0, 5.0]
    # Calendar mode has no threshold table.
    assert dss.effective_bluestar_thresholds(s, dss.CALENDAR_GATING) == []
    # No override → loads shipped defaults.
    assert dss.effective_bluestar_thresholds(s, "Non-Payer")


# ─── Season helpers ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("day,expected_idx", [
    (0, 0), (1, 0), (28, 0), (29, 1), (56, 1), (57, 2),
])
def test_season_index(day, expected_idx):
    assert sp.season_index(day, 28) == expected_idx


@pytest.mark.parametrize("day,expected", [
    (0, 0), (1, 1), (28, 28), (29, 1), (30, 2),
])
def test_day_in_season(day, expected):
    assert sp.day_in_season(day, 28) == expected


def test_days_left_in_season():
    assert sp.days_left_in_season(1, 28) == 27
    assert sp.days_left_in_season(28, 28) == 0   # last day of the season
    assert sp.days_left_in_season(29, 28) == 27  # new season
    assert sp.days_left_in_season(0, 28) == 28   # install day


# ─── Infinite pack ───────────────────────────────────────────────────────────

def test_open_infinite_pack_opens_two_t1():
    config = load_defaults()
    game_state = init_state(config)
    rng = Random(3)
    results = sp.open_infinite_pack(game_state, config, rng)
    assert len(results) == sp.INFINITE_PACK_COUNT == 2
    for r in results:
        assert r["final_tier"] == sp.INFINITE_PACK_TIER == "StandardPackT1"
