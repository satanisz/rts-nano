"""Serializable observation snapshots for headless consumers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

from rts_nano.game.assets.entities import TeamColor

if TYPE_CHECKING:
    from rts_nano.game.assets.entities.base_entities import Entity
    from rts_nano.game.manager import EntitiesGroup, GameManager

type EntityId = str


@dataclass(frozen=True, slots=True)
class TeamSnapshot:
    """Serializable team economy and population summary."""

    team: str
    wood: int
    cristal: int
    units: int
    buildings: int


@dataclass(frozen=True, slots=True)
class EntitySnapshot:
    """Immutable public view of a game entity."""

    id: EntityId
    kind: str
    team: str | None
    x: float
    y: float
    life: int
    max_life: int | None
    amount: int | None
    state: str | None
    carry_wood: int
    carry_cristal: int
    selected: bool


@dataclass(frozen=True, slots=True)
class Observation:
    """Deterministic, serializable state snapshot for AI callers."""

    tick: int
    map_width: int
    map_height: int
    current_team: str
    game_over: str | None
    teams: tuple[TeamSnapshot, ...]
    entities: tuple[EntitySnapshot, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a plain dictionary suitable for JSON serialization."""
        return asdict(self)


class EntityIdRegistry:
    """Assign stable snapshot IDs to live entities for one environment run."""

    def __init__(self) -> None:
        """Initialize an empty entity ID registry."""
        self._entity_ids: dict[Entity, EntityId] = {}
        self._next_entity_id = 0

    def reset(self) -> None:
        """Forget all entity IDs, usually after environment reset."""
        self._entity_ids.clear()
        self._next_entity_id = 0

    def id_for(self, entity: Entity) -> EntityId:
        """Return the existing or newly assigned snapshot ID for an entity."""
        entity_id = self._entity_ids.get(entity)
        if entity_id is None:
            self._next_entity_id += 1
            entity_id = f"e{self._next_entity_id:04d}"
            self._entity_ids[entity] = entity_id
        return entity_id

    def entity_by_id(self, manager: GameManager, entity_id: EntityId) -> Entity:
        """Resolve a snapshot ID back to the live entity in the current manager."""
        for entity in manager.all_entities:
            if self.id_for(entity) == entity_id:
                return entity
        raise KeyError(f"Unknown entity id: {entity_id}")


def build_observation(manager: GameManager, tick: int, registry: EntityIdRegistry) -> Observation:
    """Build a deterministic serializable snapshot from a game manager."""
    return Observation(
        tick=tick,
        map_width=manager.map_width,
        map_height=manager.map_height,
        current_team=manager.current_team.value,
        game_over=manager.game_over_message,
        teams=tuple(
            _snapshot_team(team, group) for team, group in manager.entities.items() if team != TeamColor.RESOURCES
        ),
        entities=tuple(_snapshot_entity(entity, registry) for entity in manager.all_entities),
    )


def _snapshot_team(team: TeamColor, group: EntitiesGroup) -> TeamSnapshot:
    return TeamSnapshot(
        team=team.value,
        wood=group.resources["wood"],
        cristal=group.resources["cristal"],
        units=len(group.peasents) + len(group.knights) + len(group.archers) + len(group.mages),
        buildings=len(group.bases),
    )


def _snapshot_entity(entity: Entity, registry: EntityIdRegistry) -> EntitySnapshot:
    team = getattr(entity, "team", None)
    return EntitySnapshot(
        id=registry.id_for(entity),
        kind=type(entity).__name__,
        team=team.value if isinstance(team, TeamColor) else None,
        x=entity.x,
        y=entity.y,
        life=entity.life,
        max_life=getattr(entity, "max_life", None),
        amount=getattr(entity, "amount", None),
        state=getattr(entity, "state", None),
        carry_wood=getattr(entity, "carry_wood", 0),
        carry_cristal=getattr(entity, "carry_cristal", 0),
        selected=entity.selected,
    )
