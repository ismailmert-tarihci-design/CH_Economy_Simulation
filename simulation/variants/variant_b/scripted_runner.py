"""Per-day executor for scripted (auto-pilot) Variant B simulations.

Given a `ScriptedRunConfig`, walks one in-progress simulation day at a time:
opens packs, claims season pass steps, beats chapters, and spends Hero
Tokens on skill-tree nodes per a configurable policy. All state mutations
go through the existing day-simulator + season-pass + skill-tree helpers
so behavior matches the manual simulator exactly.
"""

from __future__ import annotations

from random import Random
from typing import Any, Dict, List, Optional, Tuple

from simulation.variants.variant_b import day_simulator as ds
from simulation.variants.variant_b import season_pass as sp
from simulation.variants.variant_b.models import (
    HeroCardConfig,
    HeroCardGameState,
    HeroDef,
    HeroProgressState,
    SkillTreeNode,
)
from simulation.variants.variant_b.hero_deck import unlock_cards
from simulation.variants.variant_b.scripted_run import ScriptedRunConfig, ScriptedRunDay
from simulation.variants.variant_b.upgrade_engine import (
    attempt_hero_upgrades,
    attempt_shared_upgrades,
)


_HERO_TOKENS = "HeroTokens"


def _hero_def(config: HeroCardConfig, hero_id: str) -> Optional[HeroDef]:
    return next((h for h in config.heroes if h.hero_id == hero_id), None)


def _next_node(hero_def: HeroDef, hero_state: HeroProgressState) -> Optional[SkillTreeNode]:
    """Return the next unactivated skill tree node, or None if tree is complete."""
    next_idx = hero_state.skill_tree_progress + 1
    if next_idx >= len(hero_def.skill_tree):
        return None
    return hero_def.skill_tree[next_idx]


def _affordable(node: SkillTreeNode, hero_level: int, tokens: int) -> bool:
    return hero_level >= node.hero_level_required and tokens >= int(node.token_cost or 0)


def _activate_one(
    hero_def: HeroDef,
    hero_state: HeroProgressState,
    game_state: HeroCardGameState,
) -> Optional[Tuple[int, List[str], str]]:
    """Activate exactly one node on a hero. Spends Hero Tokens. Returns the
    activation tuple `(node_index, card_ids, perk_label)` or None when no
    affordable next node exists."""
    next_node = _next_node(hero_def, hero_state)
    if next_node is None:
        return None
    tokens = int(game_state.bonus_items.get(_HERO_TOKENS, 0))
    if not _affordable(next_node, hero_state.level, tokens):
        return None
    cost = int(next_node.token_cost or 0)
    if cost > 0:
        game_state.bonus_items[_HERO_TOKENS] = tokens - cost
    hero_state.skill_tree_progress = next_node.node_index
    unlock_cards(hero_state, next_node.cards_unlocked)
    return (next_node.node_index, list(next_node.cards_unlocked), next_node.perk_label)


def _spend_tokens(
    game_state: HeroCardGameState,
    config: HeroCardConfig,
    scripted_cfg: ScriptedRunConfig,
) -> List[Tuple[str, int, str]]:
    """Apply the configured spend policy. Returns [(hero_id, node_index, perk), ...]."""
    activations: List[Tuple[str, int, str]] = []
    hero_ids = list(game_state.heroes.keys())
    if not hero_ids:
        return activations

    if scripted_cfg.token_spend_policy == "focus_hero":
        target = scripted_cfg.focus_hero_id
        if not target or target not in game_state.heroes:
            return activations
        hero_def = _hero_def(config, target)
        if hero_def is None:
            return activations
        while True:
            tokens = int(game_state.bonus_items.get(_HERO_TOKENS, 0))
            nxt = _next_node(hero_def, game_state.heroes[target])
            if nxt is None or not _affordable(nxt, game_state.heroes[target].level, tokens):
                break
            act = _activate_one(hero_def, game_state.heroes[target], game_state)
            if act is None:
                break
            activations.append((target, act[0], act[2]))
        return activations

    if scripted_cfg.token_spend_policy == "round_robin":
        made_progress = True
        while made_progress:
            made_progress = False
            for hid in hero_ids:
                hero_def = _hero_def(config, hid)
                if hero_def is None:
                    continue
                tokens = int(game_state.bonus_items.get(_HERO_TOKENS, 0))
                nxt = _next_node(hero_def, game_state.heroes[hid])
                if nxt is None or not _affordable(nxt, game_state.heroes[hid].level, tokens):
                    continue
                act = _activate_one(hero_def, game_state.heroes[hid], game_state)
                if act is not None:
                    activations.append((hid, act[0], act[2]))
                    made_progress = True
        return activations

    # cheapest_first (default): pick the cheapest affordable next-node across all heroes
    while True:
        tokens = int(game_state.bonus_items.get(_HERO_TOKENS, 0))
        candidates: List[Tuple[int, str, HeroDef]] = []
        for hid in hero_ids:
            hero_def = _hero_def(config, hid)
            if hero_def is None:
                continue
            nxt = _next_node(hero_def, game_state.heroes[hid])
            if nxt is None:
                continue
            if not _affordable(nxt, game_state.heroes[hid].level, tokens):
                continue
            candidates.append((int(nxt.token_cost or 0), hid, hero_def))
        if not candidates:
            break
        candidates.sort(key=lambda x: (x[0], x[1]))
        cost, hid, hero_def = candidates[0]
        act = _activate_one(hero_def, game_state.heroes[hid], game_state)
        if act is None:
            break  # Guard against pathological non-progress
        activations.append((hid, act[0], act[2]))
    return activations


def _claim_season_pass_to(
    target_step: int,
    state: Dict[str, Any],
    game_state: HeroCardGameState,
    config: HeroCardConfig,
    rng: Random,
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Claim season pass steps up to and including target_step. Mutates state["season_pass_step"]."""
    lines: List[str] = []
    opened: List[Dict[str, Any]] = []
    if target_step is None or target_step <= 0:
        return lines, opened
    if target_step > len(sp.SEASON_PASS_TABLE):
        target_step = len(sp.SEASON_PASS_TABLE)
    while state["season_pass_step"] <= target_step:
        ok, step_lines, step_opened = sp.apply_season_pass_step(
            state["season_pass_step"], state.get("paid_pass", False),
            game_state, state["extras"], config=config, rng=rng,
        )
        if not ok:
            break
        lines.extend(step_lines)
        opened.extend(step_opened)
        state["season_pass_step"] += 1
    return lines, opened


def run_one_day(
    state: Dict[str, Any],
    config: HeroCardConfig,
    scripted_cfg: ScriptedRunConfig,
    day_entry: Optional[ScriptedRunDay],
    rng: Random,
) -> Dict[str, Any]:
    """Run a single scripted day. Returns a summary dict for the activity log.

    `state` is the day-simulator session state dict (same shape as
    `app_pages/variant_b_day_simulator.py` uses), so the runner can advance
    the season-pass step counter, RNG, etc. The caller is responsible for
    handling FTUE on D0 and advancing the day counter between calls.
    """
    game_state: HeroCardGameState = state["game_state"]
    lines: List[str] = []
    opened_packs: List[Dict[str, Any]] = []

    if scripted_cfg.auto_open_daily_packs:
        results = ds.open_daily_bundle(game_state, config, rng)
        opened_packs.extend(results)
        lines.append(f"Daily bundle opened: {len(results)} packs")
        # Mark all daily slots used so the manual UI doesn't re-fire them.
        state.setdefault("daily_used", set()).update(
            {"bundle", "t2", "t1_0", "t1_1", "t1_2"}
        )

    chapters = day_entry.chapters_beaten if day_entry else 0
    for i in range(int(chapters)):
        r = ds.open_pack_by_name("EndOfChapterPack", game_state, config, rng, apply_evolution=False)
        opened_packs.append(r)
        game_state.chapters_beaten += 1
        lines.append(f"Beat chapter #{game_state.chapters_beaten} → EndOfChapter pack opened")

    target = day_entry.season_pass_target_step if day_entry else None
    if target is not None:
        sp_lines, sp_opened = _claim_season_pass_to(int(target), state, game_state, config, rng)
        lines.extend(sp_lines)
        opened_packs.extend(sp_opened)

    # Auto-upgrade cards greedily. Upgrades drive hero level-ups which unlock
    # new skill-tree nodes (the upgrade engine debits tokens via
    # check_and_advance_skill_tree). This mirrors the orchestrator's daily flow.
    upgrade_events, total_xp, total_bs, _tree_acts = attempt_hero_upgrades(game_state, config)
    shared_events, shared_bs = attempt_shared_upgrades(game_state, config)
    if upgrade_events or shared_events:
        lines.append(
            f"Auto-upgrades: {len(upgrade_events)} hero (+{total_xp} XP, +{total_bs} bluestars), "
            f"{len(shared_events)} shared (+{shared_bs} bluestars)"
        )

    # After level-ups, sweep leftover tokens by the configured policy.
    activations = _spend_tokens(game_state, config, scripted_cfg)
    if activations:
        lines.append(
            f"Spent tokens on {len(activations)} skill node(s): "
            + ", ".join(f"{hid}#{idx}" for hid, idx, _ in activations[:10])
            + ("…" if len(activations) > 10 else "")
        )

    return {
        "log_lines": lines,
        "opened_packs": opened_packs,
        "activations": activations,
        "hero_upgrades": len(upgrade_events),
        "shared_upgrades": len(shared_events),
    }
