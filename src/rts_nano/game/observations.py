"""Serializable observation snapshots for headless consumers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING

from rts_nano.simulation.entities import TeamColor
from rts_nano.simulation.entities.base import Building
from rts_nano.simulation.entities.units import CasterUnit

if TYPE_CHECKING:
    from rts_nano.application import GameSession
    from rts_nano.game.state import TeamState
    from rts_nano.simulation.entities.base import Entity

type EntityId = str

OBSERVATION_SCHEMA_VERSION = 4
"""Version of the observation contract. Bump when fields change meaning.

v2: added ``shield`` / ``shield_max`` to ``EntitySnapshot`` (AEGIS shield buffer).
v3: added faction/upgrade state and typed building activity queues.
v4: added Mage energy, cooldown, and unlocked-ability state.
"""


@dataclass(frozen=True, slots=True)
class TeamSnapshot:
    """Serializable team economy and population summary."""

    team: str
    wood: int
    gold: int
    units: int
    buildings: int
    population_cap: int
    queued_units: int
    faction_id: str = ""
    completed_upgrades: tuple[str, ...] = ()
    reserved_upgrades: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProductionSnapshot:
    """Serializable view of one queued production job."""

    unit_type: str
    remaining_frames: int
    total_frames: int
    progress: float


@dataclass(frozen=True, slots=True)
class ActivitySnapshot:
    """Serializable view of one unit-production or research activity."""

    kind: str
    content_id: str
    remaining_frames: int
    total_frames: int
    progress: float


@dataclass(frozen=True, slots=True)
class AbilitySnapshot:
    """Action-facing state for one currently unlocked caster ability."""

    ability_id: str
    target_kind: str
    energy_cost: int
    cooldown_frames: int
    cooldown_remaining: int
    energy_ready: bool


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
    shield: int
    shield_max: int
    amount: int | None
    state: str | None
    carry_wood: int
    carry_gold: int
    selected: bool
    production_queue: tuple[ProductionSnapshot, ...]
    activity_queue: tuple[ActivitySnapshot, ...] = ()
    is_under_construction: bool = False
    construction_progress: float | None = None
    order: str | None = None
    energy: int | None = None
    energy_max: int | None = None
    abilities: tuple[AbilitySnapshot, ...] = ()


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
    schema_version: int = OBSERVATION_SCHEMA_VERSION

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

    def entity_by_id(self, manager: GameSession, entity_id: EntityId) -> Entity:
        """Resolve a snapshot ID back to the live entity in the current manager."""
        for entity in manager.all_entities:
            if self.id_for(entity) == entity_id:
                return entity
        raise KeyError(f"Unknown entity id: {entity_id}")


def build_observation(manager: GameSession, tick: int, registry: EntityIdRegistry) -> Observation:
    """Build a deterministic serializable snapshot from a game manager."""
    return Observation(
        tick=tick,
        map_width=manager.map_width,
        map_height=manager.map_height,
        current_team=manager.current_team.value,
        game_over=manager.game_over_message,
        teams=tuple(_snapshot_team(manager, team, team_state) for team, team_state in manager.teams.items()),
        entities=tuple(_snapshot_entity(manager, entity, registry) for entity in manager.all_entities),
    )


def _snapshot_team(manager: GameSession, team: TeamColor, team_state: TeamState) -> TeamSnapshot:
    return TeamSnapshot(
        team=team.value,
        wood=team_state.resources["wood"],
        gold=team_state.resources["gold"],
        units=len(manager.state.units_for_team(team)),
        buildings=len(manager.state.buildings_for_team(team)),
        population_cap=manager.population_cap_for_team(team),
        queued_units=manager.production.queued_units_for_team(team),
        faction_id=str(team_state.faction_id),
        completed_upgrades=tuple(str(item) for item in team_state.completed_upgrades),
        reserved_upgrades=tuple(str(item) for item in team_state.reserved_upgrades),
    )


def _snapshot_entity(manager: GameSession, entity: Entity, registry: EntityIdRegistry) -> EntitySnapshot:
    team = getattr(entity, "team", None)
    current_order = getattr(entity, "current_order", None)
    building = entity if isinstance(entity, Building) else None
    caster = entity if isinstance(entity, CasterUnit) else None
    return EntitySnapshot(
        id=registry.id_for(entity),
        kind=type(entity).__name__,
        team=team.value if isinstance(team, TeamColor) else None,
        x=entity.x,
        y=entity.y,
        life=entity.life,
        max_life=getattr(entity, "max_life", None),
        shield=entity.shield,
        shield_max=entity.shield_max,
        amount=getattr(entity, "amount", None),
        state=getattr(entity, "state", None),
        carry_wood=getattr(entity, "carry_wood", 0),
        carry_gold=getattr(entity, "carry_gold", 0),
        selected=entity in manager.selected_entities,
        production_queue=_snapshot_production_queue(manager, building) if building is not None else (),
        activity_queue=_snapshot_activity_queue(manager, building) if building is not None else (),
        is_under_construction=building is not None and building.is_under_construction,
        construction_progress=building.construction_progress if building is not None else None,
        order=current_order.kind if current_order is not None else None,
        energy=caster.energy if caster is not None else None,
        energy_max=caster.energy_max if caster is not None else None,
        abilities=_snapshot_abilities(manager, caster) if caster is not None else (),
    )


def _snapshot_production_queue(manager: GameSession, building: Building) -> tuple[ProductionSnapshot, ...]:
    return tuple(
        ProductionSnapshot(
            unit_type=item.unit_type,
            remaining_frames=item.remaining_frames,
            total_frames=item.total_frames,
            progress=item.progress,
        )
        for item in manager.production.queue_for(building)
        if item.kind == "unit"
    )


def _snapshot_activity_queue(manager: GameSession, building: Building) -> tuple[ActivitySnapshot, ...]:
    return tuple(
        ActivitySnapshot(
            kind=item.kind,
            content_id=item.content_id,
            remaining_frames=item.remaining_frames,
            total_frames=item.total_frames,
            progress=item.progress,
        )
        for item in manager.production.queue_for(building)
    )


def _snapshot_abilities(manager: GameSession, caster: CasterUnit) -> tuple[AbilitySnapshot, ...]:
    return tuple(
        AbilitySnapshot(
            ability_id=str(ability.id),
            target_kind=ability.target_kind.value,
            energy_cost=ability.energy_cost,
            cooldown_frames=ability.cooldown_frames,
            cooldown_remaining=caster.ability_cooldowns.get(str(ability.id), 0),
            energy_ready=caster.energy >= ability.energy_cost and caster.ability_cooldowns.get(str(ability.id), 0) == 0,
        )
        for ability in manager.abilities.available_abilities(caster)
    )
