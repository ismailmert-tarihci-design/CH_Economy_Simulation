"""
Tests for coin economy tracking and calculations.
"""

import pytest

from simulation.coin_economy import (
    CoinLedger,
    CoinTransaction,
    can_afford_upgrade,
    compute_coin_income,
    compute_upgrade_coin_cost,
)
from simulation.models import (
    Card,
    CardCategory,
    CoinPerDuplicate,
    ProgressionMapping,
    SimConfig,
    UpgradeTable,
)


@pytest.fixture
def sim_config():
    """Create a test SimConfig with coin and upgrade tables."""
    upgrade_tables = {
        CardCategory.GOLD_SHARED: UpgradeTable(
            category=CardCategory.GOLD_SHARED,
            duplicate_costs=[1] * 100,
            coin_costs=[100 + i * 100 for i in range(100)],  # 100, 200, 300, ...
            bluestar_rewards=[1] * 100,
        ),
        CardCategory.BLUE_SHARED: UpgradeTable(
            category=CardCategory.BLUE_SHARED,
            duplicate_costs=[2] * 100,
            coin_costs=[150 + i * 100 for i in range(100)],
            bluestar_rewards=[1] * 100,
        ),
        CardCategory.UNIQUE: UpgradeTable(
            category=CardCategory.UNIQUE,
            duplicate_costs=[3] * 10,
            coin_costs=[500 + i * 500 for i in range(10)],
            bluestar_rewards=[1] * 10,
        ),
    }

    coin_per_duplicate = {
        CardCategory.GOLD_SHARED: CoinPerDuplicate(
            category=CardCategory.GOLD_SHARED,
            coins_per_dupe=[10, 12, 14, 16, 18, 20] + [20] * 94,
        ),
        CardCategory.BLUE_SHARED: CoinPerDuplicate(
            category=CardCategory.BLUE_SHARED,
            coins_per_dupe=[15, 18, 21, 24, 27, 30] + [30] * 94,
        ),
        CardCategory.UNIQUE: CoinPerDuplicate(
            category=CardCategory.UNIQUE,
            coins_per_dupe=[25, 30, 35, 40, 45, 50, 55, 60, 65, 70],
        ),
    }

    return SimConfig(
        packs=[],
        upgrade_tables=upgrade_tables,
        duplicate_ranges={},
        coin_per_duplicate=coin_per_duplicate,
        progression_mapping=ProgressionMapping(
            shared_levels=[1, 2, 3, 4, 5] + list(range(6, 101)),
            unique_levels=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        ),
        unique_unlock_schedule={},
        pack_averages={},
        num_days=30,
        base_shared_rate=0.70,
        base_unique_rate=0.30,
        max_shared_level=100,
        max_unique_level=10,
    )


class TestComputeCoinIncome:
    """Tests for compute_coin_income function."""

    def test_income_gold_shared_level_5_8_dupes(self, sim_config):
        """Gold Shared level 5 with 8 duplicates should return 18*8=144 coins."""
        card = Card(
            id="card_1",
            name="Gold Card",
            category=CardCategory.GOLD_SHARED,
            level=5,
        )
        income = compute_coin_income(card, 8, sim_config)
        assert income == 144  # coins_per_dupe[4] * 8 = 18 * 8

    def test_income_gold_shared_level_1_10_dupes(self, sim_config):
        """Gold Shared level 1 with 10 duplicates should return 10*10=100 coins."""
        card = Card(
            id="card_1",
            name="Gold Card",
            category=CardCategory.GOLD_SHARED,
            level=1,
        )
        income = compute_coin_income(card, 10, sim_config)
        assert income == 100  # coins_per_dupe[0] * 10 = 10 * 10

    def test_income_blue_shared_level_3_5_dupes(self, sim_config):
        """Blue Shared level 3 with 5 duplicates should return 21*5=105 coins."""
        card = Card(
            id="card_2",
            name="Blue Card",
            category=CardCategory.BLUE_SHARED,
            level=3,
        )
        income = compute_coin_income(card, 5, sim_config)
        assert income == 105  # coins_per_dupe[2] * 5 = 21 * 5

    def test_income_unique_level_2_3_dupes(self, sim_config):
        """Unique level 2 with 3 duplicates should return 30*3=90 coins."""
        card = Card(
            id="card_3",
            name="Unique Card",
            category=CardCategory.UNIQUE,
            level=2,
        )
        income = compute_coin_income(card, 3, sim_config)
        assert income == 90  # coins_per_dupe[1] * 3 = 30 * 3

    def test_income_maxed_gold_shared(self, sim_config):
        """Maxed Gold Shared (level 100) should return flat reward (10 coins)."""
        card = Card(
            id="card_1",
            name="Gold Card",
            category=CardCategory.GOLD_SHARED,
            level=100,
        )
        income = compute_coin_income(card, 8, sim_config)
        assert income == 10  # Flat reward: coins_per_dupe[0]

    def test_income_maxed_unique(self, sim_config):
        """Maxed Unique (level 10) should return flat reward (25 coins)."""
        card = Card(
            id="card_3",
            name="Unique Card",
            category=CardCategory.UNIQUE,
            level=10,
        )
        income = compute_coin_income(card, 5, sim_config)
        assert income == 25  # Flat reward: coins_per_dupe[0]

    def test_income_zero_dupes(self, sim_config):
        """Card with 0 duplicates should earn 0 coins."""
        card = Card(
            id="card_1",
            name="Gold Card",
            category=CardCategory.GOLD_SHARED,
            level=2,
        )
        income = compute_coin_income(card, 0, sim_config)
        assert income == 0


class TestComputeUpgradeCoinCost:
    """Tests for compute_upgrade_coin_cost function."""

    def test_upgrade_cost_gold_shared_level_1(self, sim_config):
        """Gold Shared level 1 upgrade cost should be 100 coins."""
        card = Card(
            id="card_1",
            name="Gold Card",
            category=CardCategory.GOLD_SHARED,
            level=1,
        )
        cost = compute_upgrade_coin_cost(card, sim_config)
        assert cost == 100

    def test_upgrade_cost_gold_shared_level_5(self, sim_config):
        """Gold Shared level 5 upgrade cost should be 500 coins."""
        card = Card(
            id="card_1",
            name="Gold Card",
            category=CardCategory.GOLD_SHARED,
            level=5,
        )
        cost = compute_upgrade_coin_cost(card, sim_config)
        assert cost == 500  # 100 + 4 * 100

    def test_upgrade_cost_blue_shared_level_2(self, sim_config):
        """Blue Shared level 2 upgrade cost should be 250 coins."""
        card = Card(
            id="card_2",
            name="Blue Card",
            category=CardCategory.BLUE_SHARED,
            level=2,
        )
        cost = compute_upgrade_coin_cost(card, sim_config)
        assert cost == 250  # 150 + 1 * 100

    def test_upgrade_cost_unique_level_3(self, sim_config):
        """Unique level 3 upgrade cost should be 1500 coins."""
        card = Card(
            id="card_3",
            name="Unique Card",
            category=CardCategory.UNIQUE,
            level=3,
        )
        cost = compute_upgrade_coin_cost(card, sim_config)
        assert cost == 1500

    def test_upgrade_cost_maxed_gold_shared(self, sim_config):
        """Maxed Gold Shared (level 100) should have 0 cost (can't upgrade)."""
        card = Card(
            id="card_1",
            name="Gold Card",
            category=CardCategory.GOLD_SHARED,
            level=100,
        )
        cost = compute_upgrade_coin_cost(card, sim_config)
        assert cost == 0

    def test_upgrade_cost_maxed_unique(self, sim_config):
        """Maxed Unique (level 10) should have 0 cost (can't upgrade)."""
        card = Card(
            id="card_3",
            name="Unique Card",
            category=CardCategory.UNIQUE,
            level=10,
        )
        cost = compute_upgrade_coin_cost(card, sim_config)
        assert cost == 0


class TestCanAffordUpgrade:
    """Tests for can_afford_upgrade function."""

    def test_can_afford_sufficient_coins(self, sim_config):
        """Player with 500 coins can afford Gold level 1 upgrade (100 cost)."""
        card = Card(
            id="card_1",
            name="Gold Card",
            category=CardCategory.GOLD_SHARED,
            level=1,
        )
        assert can_afford_upgrade(500, card, sim_config) is True

    def test_cannot_afford_insufficient_coins(self, sim_config):
        """Player with 50 coins cannot afford Gold level 1 upgrade (100 cost)."""
        card = Card(
            id="card_1",
            name="Gold Card",
            category=CardCategory.GOLD_SHARED,
            level=1,
        )
        assert can_afford_upgrade(50, card, sim_config) is False

    def test_can_afford_exact_coins(self, sim_config):
        """Player with 100 coins can afford Gold level 1 upgrade (100 cost)."""
        card = Card(
            id="card_1",
            name="Gold Card",
            category=CardCategory.GOLD_SHARED,
            level=1,
        )
        assert can_afford_upgrade(100, card, sim_config) is True

    def test_can_afford_maxed_card(self, sim_config):
        """Player can "afford" maxed card (0 cost)."""
        card = Card(
            id="card_1",
            name="Gold Card",
            category=CardCategory.GOLD_SHARED,
            level=100,
        )
        assert can_afford_upgrade(0, card, sim_config) is True


class TestCoinLedger:
    """Tests for CoinLedger class."""

    def test_add_income(self):
        """Adding income should increase balance."""
        ledger = CoinLedger()
        ledger.add_income(100, "card_1", 1)
        assert ledger.balance == 100
        assert len(ledger.transactions) == 1
        assert ledger.transactions[0].source == "income"

    def test_spend_success(self):
        """Spending when balance sufficient should decrease balance."""
        ledger = CoinLedger(balance=100)
        result = ledger.spend(30, "card_1", 1)
        assert result is True
        assert ledger.balance == 70
        assert len(ledger.transactions) == 1
        assert ledger.transactions[0].source == "spend"

    def test_spend_failure_insufficient_balance(self):
        """Spending when balance insufficient should fail and not change balance."""
        ledger = CoinLedger(balance=50)
        result = ledger.spend(100, "card_1", 1)
        assert result is False
        assert ledger.balance == 50  # Balance unchanged
        assert len(ledger.transactions) == 0  # No transaction recorded

    def test_spend_exact_balance(self):
        """Spending exact balance should succeed."""
        ledger = CoinLedger(balance=50)
        result = ledger.spend(50, "card_1", 1)
        assert result is True
        assert ledger.balance == 0

    def test_daily_summary_single_day(self):
        """Daily summary should aggregate all transactions for a day."""
        ledger = CoinLedger()
        ledger.add_income(100, "card_1", 1)
        ledger.add_income(50, "card_2", 1)
        ledger.spend(30, "card_3", 1)
        ledger.spend(20, "card_4", 1)

        summary = ledger.daily_summary(1)
        assert summary["total_income"] == 150
        assert summary["total_spent"] == 50
        assert summary["balance"] == 100

    def test_daily_summary_multiple_days(self):
        """Daily summary should only include transactions for specified day."""
        ledger = CoinLedger()
        ledger.add_income(100, "card_1", 1)
        ledger.spend(30, "card_1", 1)
        ledger.add_income(200, "card_2", 2)
        ledger.spend(50, "card_2", 2)

        summary_day1 = ledger.daily_summary(1)
        assert summary_day1["total_income"] == 100
        assert summary_day1["total_spent"] == 30
        assert summary_day1["balance"] == 220

        summary_day2 = ledger.daily_summary(2)
        assert summary_day2["total_income"] == 200
        assert summary_day2["total_spent"] == 50
        assert summary_day2["balance"] == 220

    def test_daily_summary_empty_day(self):
        """Daily summary for day with no transactions should return zeros."""
        ledger = CoinLedger(balance=100)
        summary = ledger.daily_summary(5)
        assert summary["total_income"] == 0
        assert summary["total_spent"] == 0
        assert summary["balance"] == 100

    def test_transaction_dataclass(self):
        """CoinTransaction should record all fields correctly."""
        txn = CoinTransaction(amount=100, source="income", card_id="card_1", day=1)
        assert txn.amount == 100
        assert txn.source == "income"
        assert txn.card_id == "card_1"
        assert txn.day == 1


class TestCoinEconomyIntegration:
    """Integration tests combining multiple components."""

    def test_full_game_day_workflow(self, sim_config):
        """Simulate a full game day: earn coins, check affordability, spend coins."""
        ledger = CoinLedger()

        ledger.add_income(500, "card_1", 1)
        assert ledger.balance == 500

        card2 = Card(
            id="card_2",
            name="Blue Card",
            category=CardCategory.BLUE_SHARED,
            level=2,
        )
        upgrade_cost = compute_upgrade_coin_cost(card2, sim_config)
        assert upgrade_cost == 250
        assert can_afford_upgrade(ledger.balance, card2, sim_config) is True

        ledger.spend(upgrade_cost, "card_2", 1)
        assert ledger.balance == 250

        summary = ledger.daily_summary(1)
        assert summary["total_income"] == 500
        assert summary["total_spent"] == 250
        assert summary["balance"] == ledger.balance

    def test_insufficient_coins_workflow(self, sim_config):
        """Workflow where player doesn't have enough coins for upgrade."""
        ledger = CoinLedger()

        # Earn only 100 coins
        card1 = Card(
            id="card_1",
            name="Gold Card",
            category=CardCategory.GOLD_SHARED,
            level=1,
        )
        income = compute_coin_income(card1, 10, sim_config)
        ledger.add_income(income, "card_1", 1)

        # Try to upgrade card with 250 cost
        card2 = Card(
            id="card_2",
            name="Blue Card",
            category=CardCategory.BLUE_SHARED,
            level=2,
        )
        upgrade_cost = compute_upgrade_coin_cost(card2, sim_config)
        assert upgrade_cost == 250

        # Cannot afford
        assert can_afford_upgrade(ledger.balance, card2, sim_config) is False

        # Spend fails
        result = ledger.spend(upgrade_cost, "card_2", 1)
        assert result is False
        assert ledger.balance == 100  # Balance unchanged
