"""Variant B orchestrator — Hero Card System daily simulation loop."""

from __future__ import annotations

from random import Random
from typing import Any, Dict, List, Optional

from simulation.models import Card, CardCategory

from simulation.variants.variant_b.models import (
    HeroCardConfig,
    HeroCardDailySnapshot,
    HeroCardGameState,
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
    compute_shared_duplicates,
    decide_hero_or_shared,
    get_coins_per_dupe,
    get_shared_coins_per_dupe,
    select_hero_card,
    select_shared_card,
)
from simulation.variants.variant_b.upgrade_engine import (
    attempt_hero_upgrades,
    attempt_shared_upgrades,
)
from simulation.variants.variant_b.premium_packs import process_premium_purchases
from simulation.variants.variant_b.hero_joker import add_jokers
from simulation.pull_logger import PullLogger, VariantBUpgradeEvent


def _resolve_card_name(config: HeroCardConfig, hero_id: str, card_id: str) -> str:
    """Look up card name from config hero definitions."""
    for hero_def in config.heroes:
        if hero_def.hero_id == hero_id:
            for card_def in hero_def.card_pool:
                if card_def.card_id == card_id:
                    return card_def.name
    return card_id


def run_simulation(
    config: HeroCardConfig,
    rng: Optional[Random] = None,
) -> HeroSimResult:
    """Run a full Variant B simulation."""
    game_state = _create_initial_state(config)
    game_state.coins = config.initial_coins

    snapshots: List[HeroCardDailySnapshot] = []
    pull_logger = PullLogger()
    total_coins_earned = 0
    total_coins_spent = 0
    all_upgrade_events: Dict[str, int] = {}

    for day in range(1, config.num_days + 1):
        game_state.day = day
        day_bluestars_start = game_state.total_bluestars
        day_coins_earned = 0
        day_coins_spent = 0
        day_jokers_received = 0
        day_cards_unlocked = 0
        day_skill_nodes: Dict[str, int] = {}
        day_pull_counts: Dict[str, int] = {}
        day_pack_counts: Dict[str, int] = {}
        day_upgrades: List[Any] = []
        day_premium_packs = 0
        day_premium_diamonds = 0
        day_hero_tokens = 0
        pull_index = 0

        # 1. Check hero unlock schedule
        _process_hero_unlocks(day, config, game_state)

        # 2. Process regular pack pulls
        num_pulls, day_pack_counts = _get_daily_pulls(day, config, game_state, rng)

        for _ in range(num_pulls):
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
                        level_before = card.level
                        dupes = compute_hero_duplicates(card.level, card.rarity, config, rng)
                        card.duplicates += dupes
                        day_pull_counts["HERO"] = day_pull_counts.get("HERO", 0) + 1

                        # Coin income from hero card dupe
                        cpd = get_coins_per_dupe(card.level, card.rarity, config)
                        coin_income = max(1, dupes * cpd)
                        game_state.coins += coin_income
                        day_coins_earned += coin_income

                        # Log the pull
                        pull_index += 1
                        pull_logger.log_pull(
                            day=day,
                            pull_index=pull_index,
                            card_id=card_id,
                            card_name=_resolve_card_name(config, hero_id, card_id),
                            card_category=f"HERO_{hero_id}",
                            card_level_before=level_before,
                            duplicates_received=dupes,
                            duplicates_total_after=card.duplicates,
                            coins_earned=coin_income,
                            pack_name="regular",
                            bluestars_earned=0,
                            upgrades=[],
                        )

                # Check joker drop
                if check_joker_drop(config, rng):
                    best_hero = _pick_joker_hero(game_state)
                    if best_hero:
                        add_jokers(game_state.heroes[best_hero], 1)
                        day_jokers_received += 1

            else:
                game_state.pity_counter += 1
                card = select_shared_card(game_state, rng)
                if card:
                    level_before = card.level
                    # Per-category duplicate computation (same formula as hero cards)
                    cat = card.category.value if hasattr(card.category, "value") else str(card.category)
                    dupes = compute_shared_duplicates(card.level, cat, config, rng)
                    card.duplicates += dupes
                    day_pull_counts[cat] = day_pull_counts.get(cat, 0) + 1

                    # Coin income from shared card dupe
                    cpd = get_shared_coins_per_dupe(card.level, cat, config)
                    coin_income = max(1, dupes * cpd)
                    game_state.coins += coin_income
                    day_coins_earned += coin_income

                    # Log the pull
                    pull_index += 1
                    pull_logger.log_pull(
                        day=day,
                        pull_index=pull_index,
                        card_id=card.id,
                        card_name=card.name,
                        card_category=cat,
                        card_level_before=level_before,
                        duplicates_received=dupes,
                        duplicates_total_after=card.duplicates,
                        coins_earned=coin_income,
                        pack_name="regular",
                        bluestars_earned=0,
                        upgrades=[],
                    )

        # 3. Process premium pack purchases
        premium_pulls, diamonds_spent, jokers_from_premium, tokens_from_premium, packs_opened = process_premium_purchases(
            day, config, game_state, rng=rng
        )
        day_premium_packs = packs_opened
        day_premium_diamonds = diamonds_spent
        day_jokers_received += jokers_from_premium
        day_hero_tokens = tokens_from_premium

        # Apply premium pull results to game state
        for pull in premium_pulls:
            if pull.get("reward_type") == "hero_tokens":
                continue
            if pull.get("reward_type") == "coins":
                game_state.coins += pull.get("reward_amount", 0)
                day_coins_earned += pull.get("reward_amount", 0)
                continue
            if pull.get("reward_type") == "bluestars":
                game_state.total_bluestars += pull.get("reward_amount", 0)
                continue
            if pull.get("reward_type"):
                continue
            if pull["is_joker"]:
                hero_id = pull["hero_id"]
                if hero_id in game_state.heroes:
                    add_jokers(game_state.heroes[hero_id], 1)
                    pull_index += 1
                    pull_logger.log_pull(
                        day=day,
                        pull_index=pull_index,
                        card_id="__joker__",
                        card_name="Hero Joker",
                        card_category=f"HERO_{hero_id}",
                        card_level_before=0,
                        duplicates_received=1,
                        duplicates_total_after=1,
                        coins_earned=0,
                        pack_name="premium",
                        bluestars_earned=0,
                        upgrades=[],
                    )
            else:
                hero_id = pull["hero_id"]
                card_id = pull["card_id"]
                if hero_id in game_state.heroes:
                    hero_state = game_state.heroes[hero_id]
                    if card_id in hero_state.cards and hero_state.cards[card_id].unlocked:
                        card_obj = hero_state.cards[card_id]
                        level_before = card_obj.level
                        card_obj.duplicates += pull["duplicates"]
                        pull_index += 1
                        pull_logger.log_pull(
                            day=day,
                            pull_index=pull_index,
                            card_id=card_id,
                            card_name=_resolve_card_name(config, hero_id, card_id),
                            card_category=f"HERO_{hero_id}",
                            card_level_before=level_before,
                            duplicates_received=pull["duplicates"],
                            duplicates_total_after=card_obj.duplicates,
                            coins_earned=0,
                            pack_name="premium",
                            bluestars_earned=0,
                            upgrades=[],
                        )

        # 4. Attempt hero card upgrades (greedy)
        upgrade_events, xp_earned, bs_earned, tree_acts = attempt_hero_upgrades(
            game_state, config
        )
        day_upgrades.extend(upgrade_events)
        day_hero_xp: Dict[str, int] = {}
        for evt in upgrade_events:
            hero_id = evt["hero_id"]
            evt_xp = evt.get("xp_earned", 0)
            day_hero_xp[hero_id] = day_hero_xp.get(hero_id, 0) + evt_xp
            day_coins_spent += evt.get("coins_spent", 0)
            key = f"{hero_id}:{evt['card_id']}"
            all_upgrade_events[key] = all_upgrade_events.get(key, 0) + 1

        for hero_id, acts in tree_acts.items():
            day_skill_nodes[hero_id] = day_skill_nodes.get(hero_id, 0) + len(acts)
            for _, card_ids, _ in acts:
                day_cards_unlocked += len(card_ids)

        # 4b. Attempt shared card upgrades (no XP, no jokers)
        shared_events, shared_bs = attempt_shared_upgrades(game_state, config)
        day_upgrades.extend(shared_events)
        for evt in shared_events:
            day_coins_spent += evt.get("coins_spent", 0)
            cat_key = evt.get("category", "SHARED")
            all_upgrade_events[cat_key] = all_upgrade_events.get(cat_key, 0) + 1

        # Attach upgrade events to the last pull of the day
        if day_upgrades and pull_logger.events and pull_logger.events[-1].day == day:
            converted_upgrades = [
                VariantBUpgradeEvent(
                    card_id=evt.get("card_id", ""),
                    old_level=evt.get("old_level", 0),
                    new_level=evt.get("new_level", 0),
                    dupes_spent=evt.get("dupes_spent", 0),
                    coins_spent=evt.get("coins_spent", 0),
                    bluestars_earned=evt.get("bluestars_earned", 0),
                    day=day,
                    hero_id=evt.get("hero_id", ""),
                    jokers_spent=evt.get("jokers_spent", 0),
                    xp_earned=evt.get("xp_earned", 0),
                )
                for evt in day_upgrades
            ]
            last_pull = pull_logger.events[-1]
            last_pull.upgrades = converted_upgrades
            last_pull.bluestars_earned = sum(u.bluestars_earned for u in converted_upgrades)

        total_coins_earned += day_coins_earned
        total_coins_spent += day_coins_spent

        # 5. Record daily snapshot
        category_avg_levels: Dict[str, float] = {}
        gold_cards = [c for c in game_state.shared_cards if getattr(c, "category", None) == CardCategory.GOLD_SHARED]
        blue_cards = [c for c in game_state.shared_cards if getattr(c, "category", None) == CardCategory.BLUE_SHARED]
        gray_cards = [c for c in game_state.shared_cards if getattr(c, "category", None) == CardCategory.GRAY_SHARED]
        if gold_cards:
            category_avg_levels["GOLD_SHARED"] = sum(c.level for c in gold_cards) / len(gold_cards)
        if blue_cards:
            category_avg_levels["BLUE_SHARED"] = sum(c.level for c in blue_cards) / len(blue_cards)
        if gray_cards:
            category_avg_levels["GRAY_SHARED"] = sum(c.level for c in gray_cards) / len(gray_cards)

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
            shared_hero_level=max((hs.level for hs in game_state.heroes.values()), default=1),
            shared_hero_xp_today=sum(day_hero_xp.values()),
            hero_xp_today=day_hero_xp,
            hero_levels={hid: hs.level for hid, hs in game_state.heroes.items()},
            hero_card_avg_levels=hero_avg_levels,
            skill_nodes_unlocked_today=day_skill_nodes,
            cards_unlocked_today=day_cards_unlocked,
            jokers_received_today=day_jokers_received,
            jokers_used_today=sum(e.get("jokers_spent", 0) for e in day_upgrades),
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
        pull_logs=pull_logger.events,
        final_shared_hero_level=max((hs.level for hs in game_state.heroes.values()), default=1),
        final_shared_hero_xp=sum(hs.xp for hs in game_state.heroes.values()),
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
        shared_hero_xp=0,
        shared_hero_level=1,
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


def _get_card_types_for_count(
    card_types_table: Dict[int, Any],
    total_unlocked: int,
) -> tuple[int, int]:
    """Floor-match total unlocked count against card_types_table thresholds.

    Returns (min, max) card types for the matching threshold.
    """
    matching_keys = [k for k in card_types_table if int(k) <= total_unlocked]
    if not matching_keys:
        best_key = min(card_types_table.keys(), key=lambda k: int(k))
    else:
        best_key = max(matching_keys, key=lambda k: int(k))
    entry = card_types_table[best_key]
    if hasattr(entry, "min"):
        return entry.min, entry.max
    return int(entry.get("min", 1)), int(entry.get("max", 3))


def _get_daily_pulls(
    day: int,
    config: HeroCardConfig,
    game_state: HeroCardGameState,
    rng: Optional[Random] = None,
) -> tuple[int, Dict[str, int]]:
    """Determine number of card pulls from pack schedule + pack type definitions.

    Uses card_types_table per pack type to scale cards with progression.
    Returns: (total_card_pulls, pack_counts_by_type)
    """
    if not config.daily_pack_schedule:
        return 0, {}

    idx = (day - 1) % len(config.daily_pack_schedule)
    day_schedule = config.daily_pack_schedule[idx]

    # Build pack type lookup by name
    from simulation.variants.variant_b.models import HeroPackType
    pack_type_map: Dict[str, HeroPackType] = {}
    for pt in config.pack_types:
        pack_type_map[pt.name] = pt

    # Count total unlocked cards across all heroes
    total_unlocked = 0
    for hero_state in game_state.heroes.values():
        for card in hero_state.cards.values():
            if card.unlocked:
                total_unlocked += 1

    total_pulls = 0
    pack_counts: Dict[str, int] = {}

    for pack_name, daily_avg in day_schedule.items():
        # Determine how many packs of this type to open
        if rng:
            # Use Python's RNG to sample Poisson without mutating numpy global state
            # Box-Muller approximation for Poisson via inverse transform
            import math
            lam = max(0.0, daily_avg)
            if lam == 0:
                num_packs = 0
            else:
                # Knuth algorithm for Poisson sampling using the simulation RNG
                L = math.exp(-lam)
                k = 0
                p = 1.0
                while p > L:
                    k += 1
                    p *= rng.random()
                num_packs = k - 1
        else:
            num_packs = round(daily_avg)

        pack_counts[pack_name] = num_packs

        # Determine cards per pack from card_types_table
        pt = pack_type_map.get(pack_name)
        if pt and pt.card_types_table:
            min_cards, max_cards = _get_card_types_for_count(pt.card_types_table, total_unlocked)
        else:
            min_cards, max_cards = 1, 3

        for _ in range(num_packs):
            if rng:
                cards_in_pack = rng.randint(min_cards, max_cards)
            else:
                cards_in_pack = (min_cards + max_cards) // 2
            total_pulls += cards_in_pack

    return total_pulls, pack_counts


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
