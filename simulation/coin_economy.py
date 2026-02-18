"""
Coin economy tracking and calculations for the Bluestar Economy Simulator.

Handles coin income from duplicates, upgrade costs, and ledger tracking.
"""

from dataclasses import dataclass, field
from typing import Dict, List

from simulation.models import Card, CardCategory, SimConfig


@dataclass
class CoinTransaction:
    """Records a single coin transaction."""

    amount: int
    source: str  # "income" or "spend"
    card_id: str
    day: int


@dataclass
class CoinLedger:
    """Tracks all coin income and spending."""

    balance: int = 0
    transactions: List[CoinTransaction] = field(default_factory=list)

    def add_income(self, amount: int, card_id: str, day: int) -> None:
        """Add coin income to the ledger."""
        self.balance += amount
        self.transactions.append(
            CoinTransaction(amount=amount, source="income", card_id=card_id, day=day)
        )

    def spend(self, amount: int, card_id: str, day: int) -> bool:
        """
        Attempt to spend coins.

        Returns True if successful, False if insufficient balance.
        Balance remains unchanged if transaction fails.
        """
        if self.balance < amount:
            return False
        self.balance -= amount
        self.transactions.append(
            CoinTransaction(amount=amount, source="spend", card_id=card_id, day=day)
        )
        return True

    def daily_summary(self, day: int) -> Dict[str, int]:
        """Get daily income and spending summary for a specific day."""
        daily_transactions = [t for t in self.transactions if t.day == day]
        total_income = sum(t.amount for t in daily_transactions if t.source == "income")
        total_spent = sum(t.amount for t in daily_transactions if t.source == "spend")
        return {
            "total_income": total_income,
            "total_spent": total_spent,
            "balance": self.balance,
        }


def compute_coin_income(card: Card, duplicates_received: int, config: SimConfig) -> int:
    """
    Calculate coin income from duplicate copies of a card.

    For maxed cards: returns flat reward of coins_per_dupe[0].
    For non-maxed cards: returns coins_per_dupe[level-1] × duplicates_received.

    Args:
        card: The card receiving duplicates
        duplicates_received: Number of duplicate copies received
        config: Simulation configuration with coin rates

    Returns:
        Total coins earned
    """
    # Determine if card is maxed (at max level for its category)
    is_maxed = False
    if card.category == CardCategory.GOLD_SHARED:
        is_maxed = card.level >= config.max_shared_level
    elif card.category == CardCategory.BLUE_SHARED:
        is_maxed = card.level >= config.max_shared_level
    elif card.category == CardCategory.UNIQUE:
        is_maxed = card.level >= config.max_unique_level

    # Get coins_per_dupe table for this category
    coin_per_dupe_data = config.coin_per_duplicate.get(card.category)
    if not coin_per_dupe_data:
        return 0

    coins_per_dupe_table = coin_per_dupe_data.coins_per_dupe

    if is_maxed:
        # Maxed cards get flat reward (first entry in table)
        return coins_per_dupe_table[0]
    else:
        # Non-maxed cards: coins × duplicates (use level-1 as index since 0-indexed)
        coins_per_dupe = coins_per_dupe_table[card.level - 1]
        return coins_per_dupe * duplicates_received


def compute_upgrade_coin_cost(card: Card, config: SimConfig) -> int:
    """
    Look up the coin cost to upgrade a card.

    Args:
        card: The card to upgrade
        config: Simulation configuration with upgrade tables

    Returns:
        Coin cost for the upgrade, or 0 if card is at max level
    """
    # Determine max level for this category
    max_level = (
        config.max_shared_level
        if card.category in (CardCategory.GOLD_SHARED, CardCategory.BLUE_SHARED)
        else config.max_unique_level
    )

    # Check if already at max level
    if card.level >= max_level:
        return 0

    # Get upgrade table for this category
    upgrade_table = config.upgrade_tables.get(card.category)
    if not upgrade_table:
        return 0

    # Get coin cost at current level (0-indexed)
    coin_costs = upgrade_table.coin_costs
    if card.level - 1 < len(coin_costs):
        return coin_costs[card.level - 1]
    return 0


def can_afford_upgrade(coins: int, card: Card, config: SimConfig) -> bool:
    """
    Check if player can afford to upgrade a card.

    Args:
        coins: Current coin balance
        card: The card to upgrade
        config: Simulation configuration

    Returns:
        True if player has enough coins, False otherwise
    """
    cost = compute_upgrade_coin_cost(card, config)
    return coins >= cost
