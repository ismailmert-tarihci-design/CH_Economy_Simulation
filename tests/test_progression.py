"""
Tests for progression and gating logic.

Test cases cover:
- Floor lookup gating at boundaries
- Progression score normalization
- Unlock schedule accumulation
"""

import pytest
from simulation.models import Card, CardCategory, ProgressionMapping
from simulation.progression import (
    can_upgrade_unique,
    compute_category_progression,
    compute_progression_score,
    get_max_unique_level,
    get_unlocked_unique_count,
)


@pytest.fixture
def progression_mapping():
    """Standard progression mapping: shared {1, 5, 10, ...} → unique {1, 2, 3, ...}"""
    return ProgressionMapping(
        shared_levels=[1, 5, 10, 20, 30, 50, 100],
        unique_levels=[1, 2, 3, 4, 5, 7, 10],
    )


class TestGetMaxUniqueLevel:
    """Test floor lookup logic for unique level gating."""

    def test_exact_boundary_shared_10_allows_unique_3(self, progression_mapping):
        # Exact match at boundary: shared=10 should map to unique=3
        result = get_max_unique_level(10, progression_mapping)
        assert result == 3

    def test_between_boundaries_shared_12_still_unique_3(self, progression_mapping):
        # Between boundaries: shared=12 is between 10 and 20, floor to 10 → unique=3
        result = get_max_unique_level(12, progression_mapping)
        assert result == 3

    def test_first_boundary_shared_1(self, progression_mapping):
        # At or below first boundary
        result = get_max_unique_level(1, progression_mapping)
        assert result == 1

    def test_below_first_boundary(self, progression_mapping):
        # Below minimum level
        result = get_max_unique_level(0.5, progression_mapping)
        assert result == 1

    def test_above_all_boundaries_shared_100(self, progression_mapping):
        # At max boundary
        result = get_max_unique_level(100, progression_mapping)
        assert result == 10


class TestComputeProgressionScore:
    """Test progression score normalization to [0, 1]."""

    def test_shared_card_50_level_equals_0_5(self, progression_mapping):
        # Shared cards normalized: 50/100 = 0.5
        card = Card(
            id="test_1",
            name="Gold Card",
            category=CardCategory.GOLD_SHARED,
            level=50,
        )
        score = compute_progression_score(card, progression_mapping)
        assert score == 0.5

    def test_unique_card_5_level_equals_0_5(self, progression_mapping):
        # Unique cards normalized: 5/10 = 0.5
        card = Card(
            id="test_2",
            name="Unique Card",
            category=CardCategory.UNIQUE,
            level=5,
        )
        score = compute_progression_score(card, progression_mapping)
        assert score == 0.5

    def test_shared_card_100_level_equals_1_0(self, progression_mapping):
        # Max shared level = 1.0
        card = Card(
            id="test_3",
            name="Max Gold",
            category=CardCategory.GOLD_SHARED,
            level=100,
        )
        score = compute_progression_score(card, progression_mapping)
        assert score == 1.0

    def test_unique_card_10_level_equals_1_0(self, progression_mapping):
        # Max unique level = 1.0
        card = Card(
            id="test_4",
            name="Max Unique",
            category=CardCategory.UNIQUE,
            level=10,
        )
        score = compute_progression_score(card, progression_mapping)
        assert score == 1.0

    def test_shared_card_0_level_equals_0(self, progression_mapping):
        card = Card(
            id="test_5",
            name="Min Gold",
            category=CardCategory.GOLD_SHARED,
            level=0,
        )
        score = compute_progression_score(card, progression_mapping)
        assert score == 0.0


class TestComputeCategoryProgression:
    """Test average progression calculation per category."""

    def test_average_gold_cards(self, progression_mapping):
        # Two gold cards at levels 50 and 100 → average 0.75
        cards = [
            Card(
                id="gold_1",
                name="Gold 1",
                category=CardCategory.GOLD_SHARED,
                level=50,
            ),
            Card(
                id="gold_2",
                name="Gold 2",
                category=CardCategory.GOLD_SHARED,
                level=100,
            ),
        ]
        avg = compute_category_progression(
            cards, CardCategory.GOLD_SHARED, progression_mapping
        )
        assert avg == 0.75

    def test_average_unique_cards(self, progression_mapping):
        # Two unique cards at levels 4 and 10 → average 0.7
        cards = [
            Card(id="u_1", name="Unique 1", category=CardCategory.UNIQUE, level=4),
            Card(id="u_2", name="Unique 2", category=CardCategory.UNIQUE, level=10),
        ]
        avg = compute_category_progression(
            cards, CardCategory.UNIQUE, progression_mapping
        )
        assert avg == 0.7

    def test_empty_category_returns_0(self, progression_mapping):
        # No cards in category
        cards = [
            Card(
                id="gold_1",
                name="Gold 1",
                category=CardCategory.GOLD_SHARED,
                level=50,
            )
        ]
        avg = compute_category_progression(
            cards, CardCategory.UNIQUE, progression_mapping
        )
        assert avg == 0.0

    def test_mixed_cards_filters_correctly(self, progression_mapping):
        # Mixed categories: should only average the BLUE_SHARED cards
        cards = [
            Card(
                id="gold_1",
                name="Gold 1",
                category=CardCategory.GOLD_SHARED,
                level=100,
            ),
            Card(
                id="blue_1", name="Blue 1", category=CardCategory.BLUE_SHARED, level=50
            ),
            Card(
                id="blue_2", name="Blue 2", category=CardCategory.BLUE_SHARED, level=100
            ),
        ]
        avg = compute_category_progression(
            cards, CardCategory.BLUE_SHARED, progression_mapping
        )
        # Should only average blue cards: (50 + 100) / 200 = 0.75
        assert avg == 0.75


class TestCanUpgradeUnique:
    """Test gating logic for unique card upgrades."""

    def test_can_upgrade_when_below_gate(self, progression_mapping):
        # Card at level 2, gate allows 3 → can upgrade
        card = Card(
            id="u_1",
            name="Unique Card",
            category=CardCategory.UNIQUE,
            level=2,
        )
        can_upgrade = can_upgrade_unique(
            card, avg_shared_level=10, mapping=progression_mapping
        )
        assert can_upgrade is True

    def test_cannot_upgrade_at_gate(self, progression_mapping):
        # Card at level 3, gate allows 3 → cannot upgrade
        card = Card(
            id="u_2",
            name="Unique Card",
            category=CardCategory.UNIQUE,
            level=3,
        )
        can_upgrade = can_upgrade_unique(
            card, avg_shared_level=10, mapping=progression_mapping
        )
        assert can_upgrade is False

    def test_cannot_upgrade_above_gate(self, progression_mapping):
        # Card at level 4, gate allows 3 → cannot upgrade (safety check)
        card = Card(
            id="u_3",
            name="Unique Card",
            category=CardCategory.UNIQUE,
            level=4,
        )
        can_upgrade = can_upgrade_unique(
            card, avg_shared_level=10, mapping=progression_mapping
        )
        assert can_upgrade is False

    def test_gate_increases_with_shared_progress(self, progression_mapping):
        # As shared_level increases, gate increases
        card = Card(
            id="u_4",
            name="Unique Card",
            category=CardCategory.UNIQUE,
            level=3,
        )
        # At shared_level=10: gate=3, can't upgrade (already at gate)
        assert not can_upgrade_unique(
            card, avg_shared_level=10, mapping=progression_mapping
        )
        # At shared_level=20: gate=4, can upgrade (level 3 < gate 4)
        assert can_upgrade_unique(
            card, avg_shared_level=20, mapping=progression_mapping
        )

    def test_raises_error_for_non_unique_card(self, progression_mapping):
        # Should only work with unique cards
        card = Card(
            id="gold_1",
            name="Gold Card",
            category=CardCategory.GOLD_SHARED,
            level=50,
        )
        with pytest.raises(
            ValueError, match="can_upgrade_unique only works with UNIQUE"
        ):
            can_upgrade_unique(card, avg_shared_level=50, mapping=progression_mapping)


class TestGetUnlockedUniqueCount:
    """Test unlock schedule accumulation."""

    def test_day_35_with_schedule_1_8_30_1(self):
        # Day 35 with {1: 8, 30: 1} → 8 + 1 = 9
        schedule = {1: 8, 30: 1}
        count = get_unlocked_unique_count(35, schedule)
        assert count == 9

    def test_day_15_with_schedule_1_8_30_1(self):
        # Day 15 with {1: 8, 30: 1} → only 1:8, so 8 (30 not reached yet)
        schedule = {1: 8, 30: 1}
        count = get_unlocked_unique_count(15, schedule)
        assert count == 8

    def test_day_1_starts_unlocks(self):
        # Day 1 with {1: 8, 30: 1} → 8
        schedule = {1: 8, 30: 1}
        count = get_unlocked_unique_count(1, schedule)
        assert count == 8

    def test_day_0_no_unlocks(self):
        # Day 0 (before any unlocks)
        schedule = {1: 8, 30: 1}
        count = get_unlocked_unique_count(0, schedule)
        assert count == 0

    def test_complex_schedule_day_100(self):
        # Complex schedule: {1: 8, 30: 1, 60: 1, 90: 1}
        schedule = {1: 8, 30: 1, 60: 1, 90: 1}
        count = get_unlocked_unique_count(100, schedule)
        assert count == 11

    def test_empty_schedule(self):
        # No unlocks scheduled
        schedule = {}
        count = get_unlocked_unique_count(100, schedule)
        assert count == 0
