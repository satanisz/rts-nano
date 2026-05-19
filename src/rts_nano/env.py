"""Public headless environment facade for AI and RL integrations."""

from __future__ import annotations

import copy
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from rts_nano.game.assets.entities import TeamColor
from rts_nano.game.assets.entities.base_entities import Building, Entity, Resource, Unit
from rts_nano.game.assets.entities.buildings import Base
from rts_nano.game.assets.entities.units import Peasant
from rts_nano.headless import HeadlessSimulation

if TYPE_CHECKING:
    from rts_nano.map_schema import MapSettings

type WorldPoint = tuple[float, float]
type EntityId = str
type ActionKind = Literal["no_op", "move", "attack", "gather", "deposit", "build", "select"]
DEFAULT_MAP_ID = "map_settings_01.json"
MAPS_DIR = Path(__file__).resolve().parent / "maps"


@dataclass(frozen=True, slots=True)
class NoOpAction:
    """Advance the simulation without issuing an order."""

    frames: int = 1


@dataclass(frozen=True, slots=True)
class MoveAction:
    """Move a team's units to a world-space destination."""

    team: TeamColor
    destination: WorldPoint
    unit_ids: tuple[EntityId, ...] = ()
    frames: int = 1


@dataclass(frozen=True, slots=True)
class AttackAction:
    """Order a team's units to attack an observed target entity."""

    team: TeamColor
    target_id: EntityId
    unit_ids: tuple[EntityId, ...] = ()
    frames: int = 1


@dataclass(frozen=True, slots=True)
class GatherAction:
    """Order a team's peasants to gather from an observed resource entity."""

    team: TeamColor
    resource_id: EntityId
    unit_ids: tuple[EntityId, ...] = ()
    frames: int = 1


@dataclass(frozen=True, slots=True)
class DepositAction:
    """Order a team's peasants to deposit resources at an observed base."""

    team: TeamColor
    base_id: EntityId | None = None
    unit_ids: tuple[EntityId, ...] = ()
    frames: int = 1


@dataclass(frozen=True, slots=True)
class BuildAction:
    """Attempt to produce a unit from a team base."""

    team: TeamColor
    base_id: EntityId | None = None
    unit_type: Literal["peasant"] = "peasant"
    frames: int = 1


@dataclass(frozen=True, slots=True)
class SelectAction:
    """Set the manager selection from entity snapshot IDs for parity with UI flows."""

    team: TeamColor
    entity_ids: tuple[EntityId, ...]
    frames: int = 1


type Action = NoOpAction | MoveAction | AttackAction | GatherAction | DepositAction | BuildAction | SelectAction


@dataclass(frozen=True, slots=True)
class ActionSpec:
    """Describe an action family currently accepted by the environment."""

    kind: ActionKind
    team: str | None = None
    target: str | None = None


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


@dataclass(frozen=True, slots=True)
class StepResult:
    """Result returned by one environment step."""

    observation: Observation
    reward: float
    done: bool
    info: dict[str, object]


type RewardFunction = Callable[[Observation], float]


class RtsNanoEnv:
    """Stable no-render facade for reinforcement-learning experiments.

    The environment owns a ``HeadlessSimulation`` internally, accepts typed
    actions, and returns immutable snapshots instead of live entity objects.
    Reward shaping is injectable so experiments can define task-specific goals
    without changing the low-level game rules.
    """

    def __init__(
        self,
        map_id: str | Path | None = DEFAULT_MAP_ID,
        *,
        settings: MapSettings | None = None,
        frame_skip: int = 1,
        reward_fn: RewardFunction | None = None,
    ) -> None:
        """Initialize an environment and load the initial simulation."""
        self._map_id = map_id
        self._settings = settings
        self._frame_skip = max(1, frame_skip)
        self._reward_fn = reward_fn
        self._seed: int | None = None
        self._simulation: HeadlessSimulation | None = None
        self._entity_ids: dict[Entity, EntityId] = {}
        self._next_entity_id = 0
        self._tick = 0
        self.reset()

    def reset(self, seed: int | None = None, map_id: str | Path | None = None) -> Observation:
        """Reset the simulation and return the initial observation.

        Args:
            seed: Optional deterministic seed reserved for current or future
                stochastic systems.
            map_id: Optional map filename, map stem, or explicit path.

        Returns:
            Initial environment observation.
        """
        if self._simulation is not None:
            self._simulation.close()

        self._seed = seed
        if map_id is not None:
            self._map_id = map_id
            self._settings = None

        self._entity_ids.clear()
        self._next_entity_id = 0
        self._tick = 0

        if self._settings is not None:
            settings_copy = copy.deepcopy(self._settings)
            self._simulation = HeadlessSimulation.from_settings(settings_copy)
        else:
            self._simulation = HeadlessSimulation.from_map_file(self._resolve_map_path(self._map_id))
        return self.observe()

    def step(self, action: Action) -> StepResult:
        """Apply an action, advance the simulation, and return the step result."""
        simulation = self._require_simulation()
        frames = max(0, self._frames_for(action) * self._frame_skip)
        self._apply_action(action)
        simulation.step(frames)
        self._tick += frames
        observation = self.observe()
        return StepResult(
            observation=observation,
            reward=self.reward(observation),
            done=self.is_done(),
            info={"tick": self._tick, "frames": frames, "seed": self._seed},
        )

    def observe(self) -> Observation:
        """Return a serializable snapshot of the current simulation state."""
        manager = self._require_simulation().manager
        teams: list[TeamSnapshot] = []
        for team, group in manager.entities.items():
            if team == TeamColor.RESOURCES:
                continue
            teams.append(
                TeamSnapshot(
                    team=team.value,
                    wood=group.resources["wood"],
                    cristal=group.resources["cristal"],
                    units=len(group.peasents) + len(group.knights) + len(group.archers) + len(group.mages),
                    buildings=len(group.bases),
                )
            )

        return Observation(
            tick=self._tick,
            map_width=manager.map_width,
            map_height=manager.map_height,
            current_team=manager.current_team.value,
            game_over=manager.game_over_message,
            teams=tuple(teams),
            entities=tuple(self._snapshot_entity(entity) for entity in manager.all_entities),
        )

    def available_actions(self) -> tuple[ActionSpec, ...]:
        """Return the action families supported by the current environment state."""
        team_names = tuple(team.team for team in self.observe().teams)
        specs: list[ActionSpec] = [ActionSpec("no_op")]
        for team_name in team_names:
            specs.extend(
                (
                    ActionSpec("move", team_name, "world_point"),
                    ActionSpec("attack", team_name, "entity_id"),
                    ActionSpec("gather", team_name, "resource_id"),
                    ActionSpec("deposit", team_name, "base_id"),
                    ActionSpec("build", team_name, "base_id"),
                    ActionSpec("select", team_name, "entity_ids"),
                )
            )
        return tuple(specs)

    def is_done(self) -> bool:
        """Return whether the current simulation has reached a terminal state."""
        return self._require_simulation().manager.game_over_message is not None

    def reward(self, observation: Observation | None = None) -> float:
        """Return the active reward value for the current observation."""
        current_observation = observation if observation is not None else self.observe()
        if self._reward_fn is None:
            return 0.0
        return self._reward_fn(current_observation)

    def close(self) -> None:
        """Close the underlying headless simulation."""
        if self._simulation is not None:
            self._simulation.close()
            self._simulation = None

    def _apply_action(self, action: Action) -> None:
        if isinstance(action, NoOpAction):
            return
        if isinstance(action, MoveAction):
            self._apply_move(action)
        elif isinstance(action, AttackAction):
            self._apply_attack(action)
        elif isinstance(action, GatherAction):
            self._apply_gather(action)
        elif isinstance(action, DepositAction):
            self._apply_deposit(action)
        elif isinstance(action, BuildAction):
            self._apply_build(action)
        elif isinstance(action, SelectAction):
            self._apply_select(action)

    def _apply_move(self, action: MoveAction) -> None:
        manager = self._require_simulation().manager
        units = self._units_for_action(action.team, action.unit_ids)
        manager._assign_group_move_order(units, (int(action.destination[0]), int(action.destination[1])))

    def _apply_attack(self, action: AttackAction) -> None:
        target = self._entity_by_id(action.target_id)
        units = self._units_for_action(action.team, action.unit_ids)
        for unit in units:
            self._require_simulation().manager._assign_unit_target(unit, target.get_center(), target)

    def _apply_gather(self, action: GatherAction) -> None:
        resource = self._entity_by_id(action.resource_id)
        if not isinstance(resource, Resource):
            raise ValueError(f"Entity is not a resource: {action.resource_id}")
        peasants = [unit for unit in self._units_for_action(action.team, action.unit_ids) if isinstance(unit, Peasant)]
        for peasant in peasants:
            self._require_simulation().manager._assign_unit_target(peasant, resource.get_center(), resource)

    def _apply_deposit(self, action: DepositAction) -> None:
        base = self._base_for_action(action.team, action.base_id)
        if base is None:
            return
        peasants = [unit for unit in self._units_for_action(action.team, action.unit_ids) if isinstance(unit, Peasant)]
        for peasant in peasants:
            self._require_simulation().manager._assign_unit_target(peasant, base.get_center(), base)

    def _apply_build(self, action: BuildAction) -> None:
        if action.unit_type != "peasant":
            raise ValueError(f"Unsupported unit type: {action.unit_type}")
        base = self._base_for_action(action.team, action.base_id)
        if base is not None:
            self._require_simulation().manager._build_peasant(base)

    def _apply_select(self, action: SelectAction) -> None:
        manager = self._require_simulation().manager
        selected = tuple(self._entity_by_id(entity_id) for entity_id in action.entity_ids)
        for entity in manager.all_entities:
            entity.selected = False
        manager.selected_entities.clear()
        for entity in selected:
            if getattr(entity, "team", None) == action.team and isinstance(entity, (Unit, Building)):
                entity.selected = True
                manager.selected_entities.append(entity)

    def _units_for_action(self, team: TeamColor, unit_ids: Iterable[EntityId]) -> list[Unit]:
        requested_ids = set(unit_ids)
        if requested_ids:
            units: list[Unit] = []
            for entity_id in requested_ids:
                entity = self._entity_by_id(entity_id)
                if isinstance(entity, Unit) and entity.team == team:
                    units.append(entity)
            return units
        return self._require_simulation().units_for_team(team)

    def _base_for_action(self, team: TeamColor, base_id: EntityId | None) -> Base | None:
        if base_id is not None:
            base = self._entity_by_id(base_id)
            if not isinstance(base, Base):
                raise ValueError(f"Entity is not a base: {base_id}")
            return base if base.team == team else None
        group = self._require_simulation().manager.entities.get(team)
        if group is None or not group.bases:
            return None
        return group.bases[0]

    def _entity_by_id(self, entity_id: EntityId) -> Entity:
        for entity in self._require_simulation().manager.all_entities:
            if self._entity_id(entity) == entity_id:
                return entity
        raise KeyError(f"Unknown entity id: {entity_id}")

    def _snapshot_entity(self, entity: Entity) -> EntitySnapshot:
        team = getattr(entity, "team", None)
        return EntitySnapshot(
            id=self._entity_id(entity),
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

    def _entity_id(self, entity: Entity) -> EntityId:
        entity_id = self._entity_ids.get(entity)
        if entity_id is None:
            self._next_entity_id += 1
            entity_id = f"e{self._next_entity_id:04d}"
            self._entity_ids[entity] = entity_id
        return entity_id

    def _require_simulation(self) -> HeadlessSimulation:
        if self._simulation is None:
            raise RuntimeError("The environment is closed. Call reset() before using it again.")
        return self._simulation

    @staticmethod
    def _frames_for(action: Action) -> int:
        return action.frames

    @staticmethod
    def _resolve_map_path(map_id: str | Path | None) -> Path:
        if map_id is None:
            map_id = DEFAULT_MAP_ID
        path = Path(map_id)
        if path.exists() or path.is_absolute():
            return path
        if path.suffix == ".json":
            return MAPS_DIR / path.name
        return MAPS_DIR / f"{path.name}.json"
