"""Variant B orchestrator — Hero Card System daily simulation loop."""

from __future__ import annotations

from random import Random
from typing import Any, Dict, List, Optional

from simulation.models import Card, CardCategory
from simulation.coin_economy import CoinLedger

from simulation.variants.variant_b.models import (
    HeroCardConfig,
    HeroCardDailySnapshot,
    HeroCardGameState,
    HeroProgressState,
    HeroSimResult,
)
from simulation.variants.variant_b.hero_deck import (
    get_unlocked_cards,
    hero_card_avg_level,
    initialize_hero,
)
from simulation.variants.variant_b.drop_algorithm import (
    check_joker_drop,
    compute_hero_duplicates,
    decide_hero_or_shared,
    get_coins_per_dupe,
    select_hero_card,
    select_shared_card,
)
from simulation.variants.variant_b.upgrade_engine import attempt_hero_upgrades
from simulation.variants.variant_b.premium_packs import process_premium_purchases
from simulation.variants.variant_b.hero_joker import add_jokers


def run_simulation(
    config: HeroCardConfig,
    rng: Optional[Random] = None,
) -> HeroSimResult:
    """Run a full Variant B simulation.

    Args:
        config: HeroCardConfig with all parameters
        rng: Random instance for MC mode (None = deterministic)

    Returns:
        HeroSimResult with daily snapshots and aggregates
    """
    game_state = _create_initial_state(config)
    coin_ledger = CoinLedger(config.initial_coins)
    game_state.coins = config.initial_coins

    snapshots: List[HeroCardDailySnapshot] = []
    total_coins_earned = 0
    total_coins_spent = 0
    all_upgrade_events: Dict[str, int] = {}

    for day in range(1, config.num_days + 1):
        game_state.day = day
        day_bluestars_start = game_state.total_bluestars
        day_coins_start = game_state.coins
        day_coins_earned = 0
        day_coins_spent = 0
        day_hero_xp: Dict[str, int] = {}
        day_jokers_received = 0
        day_jokers_used = 0
        day_cards_unlocked = 0
        day_skill_nodes: Dict[str, int] = {}
        day_pull_counts: Dict[str, int] = {}
        day_pack_counts: Dict[str, int] = {}
        day_upgrades: List[Any] = []
        day_premium_packs = 0
        day_premium_diamonds = 0
        day_hero_tokens = 0

        # 1. Check hero unlock schedule
        _process_hero_unlocks(day, config, game_state)

        # 2. Process regular pack pulls
        num_pulls = _get_daily_pulls(day, config, rng)
        day_pack_counts["regular"] = num_pulls

        for pull_idx in range(num_pulls):
            pull_type = decide_hero_or_shared(game_state, config, rng)

            if pull_type == "hero":
                game_state.pity_counter = 0
                result = select_hero_card(game_state, config, rng)
                if result:
                    hero_id, card_id = result

                    # Update anti-streak tracking
                    if hero_id == game_state.last_hero_pulled:
                        game_state.hero_streak_count += 1
                    else:
                        game_state.last_hero_pulled = hero_id
                        game_state.hero_streak_count = 1

                    hero_state = game_state.heroes[hero_id]
                    card = hero_state.cards.get(card_id)
                    if card:
                        dupes = compute_hero_duplicates(card.level, card.rarity, config, rng)
                        card.duplicates += dupes
                        day_pull_counts["HERO"] = day_pull_counts.get("HERO", 0) + 1

                        # Coin income from hero card dupe (per-level, per-rarity)
                        cpd = get_coins_per_dupe(card.level, card.rarity, config)
                        coin_income = max(1, dupes * cpd)
                        game_state.coins += coin_income
                        day_coins_earned += coin_income

                # Check joker drop
                if check_joker_drop(config, rng):
                    # Give joker to the hero with the most unlocked cards
                    best_hero = _pick_joker_hero(game_state)
                    if best_hero:
                        add_jokers(game_state.heroes[best_hero], 1)
                        day_jokers_received += 1

            else:
                game_state.pity_counter += 1
                card = select_shared_card(game_state, rng)
                if card:
                    card.duplicates += 1
                    cat = card.category.value if hasattr(card, "category") else "SHARED"
                    day_pull_counts[cat] = day_pull_counts.get(cat, 0) + 1

                    coin_income = max(1, 5)
                    game_state.coins += coin_income
                    day_coins_earned += coin_income

        # 3. Process premium pack purchases (uses same dupe % mechanic)
        premium_pulls, diamonds_spent, jokers_from_premium, tokens_from_premium = process_premium_purchases(
            day, config, game_state, rng=rng
        )
        day_premium_packs = len(premium_pulls)
        day_premium_diamonds = diamonds_spent
        day_jokers_received += jokers_from_premium
        day_hero_tokens = tokens_from_premium

        # Apply premium pull results to game state
        for pull in premium_pulls:
            if pull.get("reward_type") == "hero_tokens":
                continue  # tracked via tokens_from_premium
            if pull.get("reward_type") == "coins":
                game_state.coins += pull.get("reward_amount", 0)
                day_coins_earned += pull.get("reward_amount", 0)
                continue
            if pull.get("reward_type") == "bluestars":
                game_state.total_bluestars += pull.get("reward_amount", 0)
                continue
            if pull.get("reward_type"):
                continue  # other reward types — tracked but not applied as coins/bluestars
            if pull["is_joker"]:
                hero_id = pull["hero_id"]
                if hero_id in game_state.heroes:
                    add_jokers(game_state.heroes[hero_id], 1)
            else:
                hero_id = pull["hero_id"]
                card_id = pull["card_id"]
                if hero_id in game_state.heroes:
                    hero_state = game_state.heroes[hero_id]
                    if card_id in hero_state.cards and hero_state.cards[card_id].unlocked:
                        hero_state.cards[card_id].duplicates += pull["duplicates"]

        # 4. Attempt hero card upgrades (greedy)
        upgrade_events, xp_earned, bs_earned, tree_acts = attempt_hero_upgrades(
            game_state, config
        )
        day_upgrades.extend(upgrade_events)
        for evt in upgrade_events:
            hero_id = evt["hero_id"]
            day_hero_xp[hero_id] = day_hero_xp.get(hero_id, 0) + evt.get("xp_earned", 0)
            day_coins_spent += evt.get("coins_spent", 0)
            key = f"{hero_id}:{evt['card_id']}"
            all_upgrade_events[key] = all_upgrade_events.get(key, 0) + 1

        for hero_id, acts in tree_acts.items():
            day_skill_nodes[hero_id] = day_skill_nodes.get(hero_id, 0) + len(acts)
            for _, card_ids, _ in acts:
                day_cards_unlocked += len(card_ids)

        # Update coin tracking
        game_state.coins -= day_coins_spent  # Already deducted in upgrade engine
        # Correction: upgrade engine already deducted coins, don't double-deduct
        game_state.coins += day_coins_spent  # Undo, since upgrade_engine handled it
        total_coins_earned += day_coins_earned
        total_coins_spent += day_coins_spent

        # 5. Record daily snapshot
        category_avg_levels: Dict[str, float] = {}
        # Shared card averages
        gold_cards = [c for c in game_state.shared_cards if c.category == CardCategory.GOLD_SHARED]
        blue_cards = [c for c in game_state.shared_cards if c.category == CardCategory.BLUE_SHARED]
        gray_cards = [c for c in game_state.shared_cards if c.category == CardCategory.GRAY_SHARED]
        if gold_cards:
            category_avg_levels["GOLD_SHARED"] = sum(c.level for c in gold_cards) / len(gold_cards)
        if blue_cards:
            category_avg_levels["BLUE_SHARED"] = sum(c.level for c in blue_cards) / len(blue_cards)
        if gray_cards:
            category_avg_levels["GRAY_SHARED"] = sum(c.level for c in gray_cards) / len(gray_cards)
        # Per-hero card averages (compute once, reuse)
        hero_avg_levels = {hid: hero_card_avg_level(hs) for hid, hs in game_state.heroes.items()}
        for hero_id, avg in hero_avg_levels.items():
            category_avg_levels[f"HERO_{hero_id}"] = avg

        snapshot = HeroCardDailySnapshot(
            day=day,
            total_bluestars=game_state.total_bluestars,
            bluestars_earned_today=game_state.total_bluestars - day_bluestars_start,
            coins_balance=game_state.coins,
            coins_earned_today=day_coins_earned,
            coins_spent_today=day_coins_spent,
            category_avg_levels=category_avg_levels,
            pull_counts_by_type=day_pull_counts,
            pack_counts_by_type=day_pack_counts,
            hero_xp_today=day_hero_xp,
            hero_levels={hid: hs.level for hid, hs in game_state.heroes.items()},
            hero_card_avg_levels=hero_avg_levels,
            skill_nodes_unlocked_today=day_skill_nodes,
            cards_unlocked_today=day_cards_unlocked,
            jokers_received_today=day_jokers_received,
            jokers_used_today=sum(e.get("jokers_spent", 0) for e in upgrade_events),
            premium_packs_opened=day_premium_packs,
            premium_diamonds_spent=day_premium_diamonds,
            hero_tokens_received=day_hero_tokens,
            upgrades_today=day_upgrades,
        )
        snapshots.append(snapshot)

    return HeroSimResult(
        daily_snapshots=snapshots,
        total_bluestars=game_state.total_bluestars,
        total_coins_earned=total_coins_earned,
        total_coins_spent=total_coins_spent,
        total_upgrades=all_upgrade_events,
        final_hero_levels={hid: hs.level for hid, hs in game_state.heroes.items()},
        final_hero_xp={hid: hs.xp for hid, hs in game_state.heroes.items()},
        total_premium_diamonds_spent=sum(s.premium_diamonds_spent for s in snapshots),
        total_jokers_received=sum(s.jokers_received_today for s in snapshots),
        total_hero_tokens=sum(s.hero_tokens_received for s in snapshots),
    )


def _create_initial_state(config: HeroCardConfig) -> HeroCardGameState:
    """Create the initial game state from config."""
    state = HeroCardGameState(
        day=0,
        coins=config.initial_coins,
        total_bluestars=config.initial_bluestars,
    )

    # Initialize shared cards (Gold + Blue + Gray)
    for i in range(1, config.num_gold_cards + 1):
        state.shared_cards.append(
            Card(id=f"gold_{i}", name=f"Gold Card {i}", category=CardCategory.GOLD_SHARED)
        )
    for i in range(1, config.num_blue_cards + 1):
        state.shared_cards.append(
            Card(id=f"blue_{i}", name=f"Blue Card {i}", category=CardCategory.BLUE_SHARED)
        )
    for i in range(1, config.num_gray_cards + 1):
        state.shared_cards.append(
            Card(id=f"gray_{i}", name=f"Gray Card {i}", category=CardCategory.GRAY_SHARED)
        )

    # Initialize heroes from day 0 unlock schedule
    for day_str, hero_ids in config.hero_unlock_schedule.items():
        if int(day_str) <= 0:
            for hero_id in hero_ids:
                hero_def = next((h for h in config.heroes if h.hero_id == hero_id), None)
                if hero_def:
                    state.heroes[hero_id] = initialize_hero(hero_def)

    return state


def _process_hero_unlocks(
    day: int,
    config: HeroCardConfig,
    game_state: HeroCardGameState,
) -> None:
    """Unlock heroes scheduled for this day."""
    hero_ids = config.hero_unlock_schedule.get(day, [])
    for hero_id in hero_ids:
        if hero_id not in game_state.heroes:
            hero_def = next((h for h in config.heroes if h.hero_id == hero_id), None)
            if hero_def:
                game_state.heroes[hero_id] = initialize_hero(hero_def)


def _get_daily_pulls(
    day: int,
    config: HeroCardConfig,
    rng: Optional[Random] = None,
) -> int:
    """Determine number of card pulls for this day from pack schedule."""
    if not config.daily_pack_schedule:
        return 0
    idx = (day - 1) % len(config.daily_pack_schedule)
    day_packs = config.daily_pack_schedule[idx]
    total = sum(day_packs.values())
    if rng:
        # Poisson-like variation
        import numpy as np
        np.random.seed(rng.randint(0, 2**31))
        return int(np.random.poisson(max(0, total)))
    return round(total)


def _pick_joker_hero(game_state: HeroCardGameState) -> Optional[str]:
    """Pick the best hero to receive a joker (most unlocked cards = most need)."""
    best_hero = None
    best_count = -1
    for hero_id, hero_state in game_state.heroes.items():
        count = len(get_unlocked_cards(hero_state))
        if count > best_count:
            best_count = count
            best_hero = hero_id
    return best_hero
