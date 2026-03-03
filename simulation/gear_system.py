from dataclasses import dataclass

from simulation.models import GameState, GearState, SimConfig


@dataclass
class GearUpgradeEvent:
    day: int
    slot_id: int
    old_level: int
    new_level: int
    designs_spent: int


def allocate_designs(designs_income: int, day: int) -> dict[int, int]:
    if designs_income < 0:
        raise ValueError("designs_income must be non-negative")

    slot_count = 6
    base = designs_income // slot_count
    remainder = designs_income % slot_count
    allocation = {slot_id: base for slot_id in range(1, slot_count + 1)}

    start = (day - 1) % slot_count
    for offset in range(remainder):
        slot_id = ((start + offset) % slot_count) + 1
        allocation[slot_id] += 1
    return allocation


def _as_gear_state(game_state: GameState) -> GearState:
    if game_state.gear_state is None:
        game_state.gear_state = GearState(
            slot_levels={slot_id: 1 for slot_id in range(1, 7)},
            design_budgets={slot_id: 0 for slot_id in range(1, 7)},
        )
    else:
        for slot_id in range(1, 7):
            game_state.gear_state.slot_levels.setdefault(slot_id, 1)
            game_state.gear_state.design_budgets.setdefault(slot_id, 0)
    return game_state.gear_state


def _build_slot_cost_map(config: SimConfig) -> dict[tuple[int, int], int]:
    gear_cfg = config.gear_system_config
    if gear_cfg is None or gear_cfg.slot_costs is None:
        raise ValueError("Missing gear_system_config.slot_costs")

    cost_map: dict[tuple[int, int], int] = {}
    for row in gear_cfg.slot_costs.cost_table:
        cost_map[(row.slot_id, row.level)] = row.design_cost
    return cost_map


def attempt_gear_upgrades(
    game_state: GameState,
    config: SimConfig,
    daily_design_allocation: dict[int, int],
) -> list[GearUpgradeEvent]:
    gear_state = _as_gear_state(game_state)
    cost_map = _build_slot_cost_map(config)

    for slot_id, amount in daily_design_allocation.items():
        if slot_id < 1 or slot_id > 6:
            raise ValueError(f"Invalid slot_id {slot_id}")
        if amount < 0:
            raise ValueError("daily design allocation must be non-negative")
        gear_state.design_budgets[slot_id] += amount

    events: list[GearUpgradeEvent] = []
    made_progress = True
    while made_progress:
        made_progress = False
        for slot_id in range(1, 7):
            current_level = gear_state.slot_levels[slot_id]
            if current_level >= 100:
                continue
            next_level = current_level + 1
            key = (slot_id, next_level)
            if key not in cost_map:
                raise ValueError(
                    f"Missing gear level-cost entry for slot {slot_id}, level {next_level}"
                )
            cost = cost_map[key]
            if gear_state.design_budgets[slot_id] < cost:
                continue

            gear_state.design_budgets[slot_id] -= cost
            gear_state.slot_levels[slot_id] = next_level
            events.append(
                GearUpgradeEvent(
                    day=game_state.day,
                    slot_id=slot_id,
                    old_level=current_level,
                    new_level=next_level,
                    designs_spent=cost,
                )
            )
            made_progress = True

    return events
