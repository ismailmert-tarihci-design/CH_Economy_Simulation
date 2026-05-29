"""Variant B orchestrator — Hero Card System daily simulation loop."""

from __future__ import annotations

from random import Random
from typing import Any, Dict, List, Optional

from simulation.models import Card, CardCategory

from simulation.variants.variant_b.models import (
    HeroCardConfig,
    HeroCardDailySnapshot,
    HeroCardGameState,
    HeroDailySnapshot,
    HeroSimResult,
)
from simulation.variants.variant_b.hero_deck import (
    get_unlocked_cards,
    hero_card_avg_level,
    initialize_hero,
    unlock_heroes_by_bluestars,
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
from simulation.variants.variant_b.pack_bonuses import (
    get_dupe_boost,
    roll_pack_bonuses,
)
from simulation.variants.variant_b.pet_gear import (
    apply_gear_pack,
    apply_pet_pack,
    gear_total_level,
    pick_pack_target,
)
from simulation.variants.variant_b import ftue, season_pass as sp
from simulation.variants.variant_b import day_simulator as ds
from simulation.variants.variant_b.chapter_schedule import (
    chapters_for_bluestars,
    chapters_for_sim_day,
)
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

    # Mirror the day-by-day simulator's D0 install-day flow: auto-run the
    # scripted FTUE (credits ~320 bluestars, ~1720 coins, Woody L4 + cards),
    # then pre-claim Season Pass steps 1–4. FTUE already opens the SP1/SP2/SP4
    # packs and credits their cards, so we skip packs in the SP catch-up and
    # only credit non-pack rewards (the +5 diamonds from SP step 3).
    extras: Dict[str, Any] = {"misc": {}}
    ftue.run_ftue(game_state, config, extras)
    for sp_step in range(1, 5):
        sp.apply_season_pass_step(
            sp_step, paid_pass=False, game_state=game_state, extras=extras,
            config=config, rng=rng, skip_packs=True,
        )
    # FTUE bluestars may already cross several unlock thresholds — bring the
    # roster up to date before day 1 so early pulls spread across all
    # progression-unlocked heroes (not just woody).
    unlock_heroes_by_bluestars(game_state, config)

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
        tokens_balance_start = int(game_state.bonus_items.get("HeroTokens", 0))
        pull_index = 0

        # 1. Check hero unlock schedule
        _process_hero_unlocks(day, config, game_state)

        # 2. Process regular pack pulls
        num_pulls, day_pack_counts, per_pack_pulls = _get_daily_pulls(day, config, game_state, rng)

        for pack_name, cards_in_pack in per_pack_pulls:
            # PetPack / GearPack: route progression to the most-recently
            # unlocked hero. These packs still run the normal card-drop loop
            # (so dupes, bonuses, and pull logs all behave consistently) —
            # the pet/gear bump is an additional effect tied to the pack type.
            if pack_name in ("PetPack", "GearPack"):
                target_hid = pick_pack_target(game_state)
                if target_hid is not None:
                    hero_target = game_state.heroes[target_hid]
                    if pack_name == "PetPack":
                        apply_pet_pack(hero_target)
                    else:
                        apply_gear_pack(hero_target)

            # Per-pack duplicate boost (shared, unique).
            shared_boost, unique_boost = get_dupe_boost(pack_name, config)

            for _ in range(cards_in_pack):
                pull_type = decide_hero_or_shared(game_state, config, rng, pull_index=pull_index)

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
                            dupes = compute_hero_duplicates(card.level, card.rarity, config, rng, boost=unique_boost)
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
                                pack_name=pack_name,
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
                        dupes = compute_shared_duplicates(card.level, cat, config, rng, boost=shared_boost)
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
                            pack_name=pack_name,
                            bluestars_earned=0,
                            upgrades=[],
                        )

            # Roll bonus items for this pack opening and credit to game_state.
            pack_bonuses_rolled = roll_pack_bonuses(pack_name, rng, config)
            for item, amount in pack_bonuses_rolled.items():
                game_state.bonus_items[item] = game_state.bonus_items.get(item, 0) + amount
                if item == "HeroTokens":
                    day_hero_tokens += int(amount)

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
                amt = int(pull.get("reward_amount", 0))
                game_state.bonus_items["HeroTokens"] = (
                    game_state.bonus_items.get("HeroTokens", 0) + amt
                )
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

        # 3b. Beat chapters. Big-simulator rule: chapter N is beaten when
        # `total_bluestars` >= `chapter_bluestar_thresholds[N-1]` (sourced
        # from CSV `avg_bs` per chapter). This replaces the legacy calendar
        # `chapters_per_day` schedule, which only stays as a fallback for
        # configs that ship no threshold table. The day-by-day simulator
        # keeps the calendar rhythm; see `app_pages/variant_b_day_simulator`.
        #
        # Each beaten chapter opens one EndOfChapterPack — same handling as
        # `scripted_runner.run_one_day` and the day-by-day UI's
        # `_auto_beat_chapters` so dupes feed today's upgrade pass.
        if config.chapter_bluestar_thresholds:
            chapters_today = chapters_for_bluestars(
                config.chapter_bluestar_thresholds,
                game_state.total_bluestars,
                game_state.chapters_beaten,
            )
        else:
            chapters_today = chapters_for_sim_day(config.chapters_per_day, day)
        if chapters_today:
            # `ds.open_pack_by_name` requires a real Random instance for
            # rarity/dupe rolls; deterministic runs (rng=None) get a fresh
            # seeded RNG so behaviour stays reproducible across days.
            chapter_rng = rng if rng is not None else Random(day)
            for _ in range(chapters_today):
                ds.open_pack_by_name(
                    "EndOfChapterPack", game_state, config, chapter_rng,
                    apply_evolution=False,
                )
                day_pack_counts["EndOfChapterPack"] = (
                    day_pack_counts.get("EndOfChapterPack", 0) + 1
                )
            game_state.chapters_beaten += chapters_today

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

        # 4a. Re-check chapter thresholds: today's upgrade bluestars may have
        # crossed additional chapter thresholds. Open EoC packs for those
        # now so the chapter count doesn't lag a day behind bluestars. Dupes
        # from these post-upgrade packs feed tomorrow's upgrade pass.
        if config.chapter_bluestar_thresholds:
            extra_chapters = chapters_for_bluestars(
                config.chapter_bluestar_thresholds,
                game_state.total_bluestars,
                game_state.chapters_beaten,
            )
            if extra_chapters:
                chapter_rng = rng if rng is not None else Random(day * 31 + 1)
                for _ in range(extra_chapters):
                    ds.open_pack_by_name(
                        "EndOfChapterPack", game_state, config, chapter_rng,
                        apply_evolution=False,
                    )
                    day_pack_counts["EndOfChapterPack"] = (
                        day_pack_counts.get("EndOfChapterPack", 0) + 1
                    )
                game_state.chapters_beaten += extra_chapters
                chapters_today += extra_chapters

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

        # Per-hero end-of-day snapshot. Total cards = sum of duplicates across
        # the hero's deck (an "ever-pulled" count would also be sensible — we
        # use dupes because that's what drives upgrades and is comparable to
        # joker_count as a resource).
        hero_states_today: Dict[str, HeroDailySnapshot] = {}
        for hid, hs in game_state.heroes.items():
            cards_by_rarity: Dict[str, int] = {}
            total_cards = 0
            for card in hs.cards.values():
                rarity_key = card.rarity.value if hasattr(card.rarity, "value") else str(card.rarity)
                cards_by_rarity[rarity_key] = cards_by_rarity.get(rarity_key, 0) + card.duplicates
                total_cards += card.duplicates
            hero_states_today[hid] = HeroDailySnapshot(
                level=hs.level,
                xp=hs.xp,
                joker_count=hs.joker_count,
                cards_by_rarity=cards_by_rarity,
                total_cards=total_cards,
                pet_level=hs.pet.level,
                gear_levels=dict(hs.gear.slot_levels),
                gear_total_level=gear_total_level(hs.gear),
            )

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
            hero_tokens_balance=int(game_state.bonus_items.get("HeroTokens", 0)),
            hero_tokens_spent_today=max(
                0,
                tokens_balance_start + day_hero_tokens
                - int(game_state.bonus_items.get("HeroTokens", 0)),
            ),
            chapters_beaten_today=chapters_today,
            chapters_beaten_total=game_state.chapters_beaten,
            hero_states=hero_states_today,
            upgrades_today=day_upgrades,
        )
        snapshots.append(snapshot)

    # `final_shared_hero_xp` reports CUMULATIVE XP earned across the run, not the
    # current remaining XP toward next level — otherwise dashboards would see this
    # number drop every time a hero levels up.
    lifetime_hero_xp = sum(s.shared_hero_xp_today for s in snapshots)

    return HeroSimResult(
        daily_snapshots=snapshots,
        total_bluestars=game_state.total_bluestars,
        total_coins_earned=total_coins_earned,
        total_coins_spent=total_coins_spent,
        total_upgrades=all_upgrade_events,
        pull_logs=pull_logger.events,
        final_shared_hero_level=max((hs.level for hs in game_state.heroes.values()), default=1),
        final_shared_hero_xp=lifetime_hero_xp,
        final_hero_levels={hid: hs.level for hid, hs in game_state.heroes.items()},
        final_hero_xp={hid: hs.xp for hid, hs in game_state.heroes.items()},
        total_premium_diamonds_spent=sum(s.premium_diamonds_spent for s in snapshots),
        total_jokers_received=sum(s.jokers_received_today for s in snapshots),
        total_hero_tokens=sum(s.hero_tokens_received for s in snapshots),
        total_hero_tokens_spent=sum(s.hero_tokens_spent_today for s in snapshots),
        final_hero_tokens_balance=int(game_state.bonus_items.get("HeroTokens", 0)),
        final_hero_skill_progress={
            hid: hs.skill_tree_progress for hid, hs in game_state.heroes.items()
        },
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
                    state.last_unlocked_hero = hero_id

    return state


def _process_hero_unlocks(
    day: int,
    config: HeroCardConfig,
    game_state: HeroCardGameState,
) -> None:
    """Unlock heroes the player's bluestars now reach (progression-gated).

    `hero_unlock_schedule` keys are total-bluestar thresholds, not days; see
    `unlock_heroes_by_bluestars`. `last_unlocked_hero` is set so PetPack /
    GearPack opens that target a "current focus" hero find one.
    """
    unlock_heroes_by_bluestars(game_state, config)


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
) -> tuple[int, Dict[str, int], List[tuple[str, int]]]:
    """Determine the day's pack openings.

    Returns: (total_card_pulls, pack_counts_by_type, per_pack_pulls)
        - total_card_pulls: total cards drawn across all packs for the day
        - pack_counts_by_type: {pack_name: num_packs_opened}
        - per_pack_pulls: [(pack_name, cards_in_this_pack), ...] in opening order
          (used by the main loop to apply per-pack bonuses + dupe boost)
    """
    if not config.daily_pack_schedule:
        return 0, {}, []

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
    per_pack_pulls: List[tuple[str, int]] = []

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
            per_pack_pulls.append((pack_name, cards_in_pack))
            total_pulls += cards_in_pack

    return total_pulls, pack_counts, per_pack_pulls


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
