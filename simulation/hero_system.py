from dataclasses import dataclass

from simulation.models import GameState, HeroState, SimConfig


@dataclass
class HeroUnlockEvent:
    day: int
    hero_id: str
    unique_cards_added: int
    total_unique_pool_after: int


def _as_hero_state(game_state: GameState) -> HeroState:
    if game_state.hero_state is None:
        game_state.hero_state = HeroState()
    return game_state.hero_state


def process_hero_unlocks(
    game_state: GameState, config: SimConfig, day: int
) -> list[HeroUnlockEvent]:
    hero_cfg = config.hero_system_config
    if hero_cfg is None or not hero_cfg.unlock_rows:
        return []

    day_rows = [row for row in hero_cfg.unlock_rows if row.day == day]
    if not day_rows:
        return []

    aggregated: dict[str, int] = {}
    for row in day_rows:
        aggregated[row.hero_id] = (
            aggregated.get(row.hero_id, 0) + row.unique_cards_added
        )

    hero_state = _as_hero_state(game_state)
    events: list[HeroUnlockEvent] = []
    for hero_id in sorted(aggregated.keys()):
        added = aggregated[hero_id]
        if hero_id not in hero_state.unlocked_heroes:
            hero_state.unlocked_heroes.append(hero_id)
        hero_state.unique_card_count += added
        events.append(
            HeroUnlockEvent(
                day=day,
                hero_id=hero_id,
                unique_cards_added=added,
                total_unique_pool_after=hero_state.unique_card_count,
            )
        )

    return events
