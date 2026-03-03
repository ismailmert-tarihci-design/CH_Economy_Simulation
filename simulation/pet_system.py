from dataclasses import dataclass
from random import Random
from typing import Optional

from simulation.models import GameState, PetState, PetTierRow, SimConfig


@dataclass
class PetSummonEvent:
    day: int
    summon_index: int
    rarity: str
    pet_id: str
    was_duplicate: bool
    owned_after: bool
    tier_after: int
    summon_count_after: int


@dataclass
class PetUpgradeEvent:
    day: int
    pet_id: str
    event_type: str
    old_value: int
    new_value: int
    resource_spent: int


def _weighted_pick(
    probabilities: dict[str, float], seed_value: int, rng: Optional[Random]
) -> str:
    entries = sorted(probabilities.items(), key=lambda item: item[0])
    total = sum(weight for _, weight in entries)
    if total <= 0:
        return entries[0][0]

    if rng is None:
        roll = (abs(seed_value) % 10000) / 10000.0 * total
    else:
        roll = rng.random() * total

    cumulative = 0.0
    for rarity, weight in entries:
        cumulative += weight
        if roll <= cumulative:
            return rarity
    return entries[-1][0]


def _as_pet_state(game_state: GameState) -> PetState:
    if game_state.pet_state is None:
        game_state.pet_state = PetState()
    return game_state.pet_state


def _get_tier_rows(config: SimConfig) -> list[PetTierRow]:
    pet_cfg = config.pet_system_config
    if pet_cfg is None or pet_cfg.tier_table is None:
        raise ValueError("Missing pet_system_config.tier_table")
    tiers = pet_cfg.tier_table.tiers
    if not tiers:
        raise ValueError("Pet tier table is empty")
    return sorted(tiers, key=lambda row: row.tier)


def _advance_tier(pet_state: PetState, tier_rows: list[PetTierRow]) -> None:
    while True:
        current = next((row for row in tier_rows if row.tier == pet_state.tier), None)
        if current is None:
            break
        threshold = current.summons_to_lvl_up
        if threshold <= 0:
            break
        if pet_state.summon_count < threshold:
            break
        if pet_state.tier >= tier_rows[-1].tier:
            break
        pet_state.tier += 1


def process_pet_summons(
    game_state: GameState,
    config: SimConfig,
    eggs_to_consume: int,
    rng: Optional[Random] = None,
) -> list[PetSummonEvent]:
    if eggs_to_consume < 0:
        raise ValueError("eggs_to_consume must be non-negative")

    if config.pet_system_config is None:
        return []
    if config.pet_system_config.tier_table is None:
        raise ValueError("Missing pet_system_config.tier_table")

    pet_state = _as_pet_state(game_state)
    tier_rows = _get_tier_rows(config)
    events: list[PetSummonEvent] = []

    for summon_index in range(1, eggs_to_consume + 1):
        _advance_tier(pet_state, tier_rows)
        tier_row = next(row for row in tier_rows if row.tier == pet_state.tier)
        rarity = _weighted_pick(
            tier_row.rarity_probabilities,
            seed_value=hash(
                (game_state.day, pet_state.summon_count, summon_index, pet_state.tier)
            ),
            rng=rng,
        )

        pet_id = f"{rarity.lower()}_pet"
        previous_duplicates = pet_state.pet_duplicates.get(pet_id, 0)
        new_duplicates = previous_duplicates + 1
        pet_state.pet_duplicates[pet_id] = new_duplicates

        if new_duplicates >= 2:
            pet_state.owned_pets[pet_id] = True

        pet_state.pet_levels.setdefault(pet_id, 1)
        pet_state.build_levels.setdefault(pet_id, 1)
        pet_state.summon_count += 1
        _advance_tier(pet_state, tier_rows)

        events.append(
            PetSummonEvent(
                day=game_state.day,
                summon_index=summon_index,
                rarity=rarity,
                pet_id=pet_id,
                was_duplicate=previous_duplicates > 0,
                owned_after=pet_state.owned_pets.get(pet_id, False),
                tier_after=pet_state.tier,
                summon_count_after=pet_state.summon_count,
            )
        )

    return events


def attempt_pet_upgrades(
    game_state: GameState,
    config: SimConfig,
    spirit_stones_available: int,
) -> tuple[list[PetUpgradeEvent], int]:
    if spirit_stones_available < 0:
        raise ValueError("spirit_stones_available must be non-negative")

    pet_cfg = config.pet_system_config
    if pet_cfg is None:
        return ([], spirit_stones_available)
    if (
        pet_cfg.level_table is None
        or pet_cfg.duplicate_table is None
        or pet_cfg.build_table is None
    ):
        return ([], spirit_stones_available)

    level_req = {
        (row.rarity, row.level): row.resource_required
        for row in pet_cfg.level_table.levels
    }
    duplicate_req = {
        (row.rarity, row.level): row.duplicates_required
        for row in pet_cfg.duplicate_table.duplicates
    }
    build_req = {
        row.build_level: row.spirit_stones_cost for row in pet_cfg.build_table.builds
    }

    pet_state = _as_pet_state(game_state)
    events: list[PetUpgradeEvent] = []

    made_progress = True
    while made_progress:
        made_progress = False
        for pet_id in sorted(pet_state.owned_pets.keys()):
            if not pet_state.owned_pets.get(pet_id, False):
                continue
            rarity = pet_id.split("_", 1)[0].capitalize()

            current_level = pet_state.pet_levels.get(pet_id, 1)
            if current_level < 100:
                target_level = current_level + 1
                req_key = (rarity, target_level)
                req_duplicates = duplicate_req.get(req_key)
                req_spirit = level_req.get(req_key)
                if req_duplicates is not None and req_spirit is not None:
                    if (
                        pet_state.pet_duplicates.get(pet_id, 0) >= req_duplicates
                        and spirit_stones_available >= req_spirit
                    ):
                        pet_state.pet_duplicates[pet_id] -= req_duplicates
                        spirit_stones_available -= req_spirit
                        pet_state.pet_levels[pet_id] = target_level
                        events.append(
                            PetUpgradeEvent(
                                day=game_state.day,
                                pet_id=pet_id,
                                event_type="level",
                                old_value=current_level,
                                new_value=target_level,
                                resource_spent=req_spirit,
                            )
                        )
                        made_progress = True
                        continue

            current_build = pet_state.build_levels.get(pet_id, 1)
            if current_build < 8:
                next_build = current_build + 1
                build_cost = build_req.get(next_build)
                if build_cost is not None and spirit_stones_available >= build_cost:
                    spirit_stones_available -= build_cost
                    pet_state.build_levels[pet_id] = next_build
                    events.append(
                        PetUpgradeEvent(
                            day=game_state.day,
                            pet_id=pet_id,
                            event_type="build",
                            old_value=current_build,
                            new_value=next_build,
                            resource_spent=build_cost,
                        )
                    )
                    made_progress = True

    return (events, spirit_stones_available)
