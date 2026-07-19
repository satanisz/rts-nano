"""Public headless environment facade for AI and RL integrations."""

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from rts_nano.action_translation import ActionTranslator
from rts_nano.actions import (
    Action,
    ActionSpec,
    AttackAction,
    AttackMoveAction,
    BuildAction,
    BuildingType,
    CancelConstructionAction,
    CancelProductionAction,
    ConstructAction,
    DepositAction,
    GatherAction,
    HoldAction,
    MoveAction,
    NoOpAction,
    PatrolAction,
    ReturnCargoAction,
    SelectAction,
    StopAction,
    WorldPoint,
)
from rts_nano.actions import (
    ActionKind as ActionKind,
)
from rts_nano.content import CONTENT
from rts_nano.game.fog import FogOfWar
from rts_nano.game.observations import (
    EntityId,
    EntityIdRegistry,
    EntitySnapshot,
    Observation,
    ProductionSnapshot,
    TeamSnapshot,
    build_observation,
)
from rts_nano.headless import HeadlessSimulation
from rts_nano.simulation.entities import TeamColor
from rts_nano.simulation.entities.base import Building, Unit
from rts_nano.simulation.entities.units import Peasant

if TYPE_CHECKING:
    from rts_nano.map_schema import MapSettings

DEFAULT_MAP_ID = "map_settings_01.json"
MAPS_DIR = Path(__file__).resolve().parent / "maps"
__all__ = [
    "Action",
    "ActionSpec",
    "AttackMoveAction",
    "AttackAction",
    "BuildingType",
    "BuildAction",
    "CancelConstructionAction",
    "CancelProductionAction",
    "ConstructAction",
    "DepositAction",
    "EntityId",
    "EntitySnapshot",
    "GatherAction",
    "HoldAction",
    "MoveAction",
    "NoOpAction",
    "Observation",
    "PatrolAction",
    "ProductionSnapshot",
    "ReturnCargoAction",
    "RtsNanoEnv",
    "SelectAction",
    "StepResult",
    "StopAction",
    "TeamSnapshot",
    "WorldPoint",
]


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
        self._entity_ids = EntityIdRegistry()
        self._action_translator: ActionTranslator | None = None
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

        self._entity_ids.reset()
        self._tick = 0

        if self._settings is not None:
            settings_copy = copy.deepcopy(self._settings)
            self._simulation = HeadlessSimulation.from_settings(settings_copy)
        else:
            self._simulation = HeadlessSimulation.from_map_file(self._resolve_map_path(self._map_id))
        self._action_translator = ActionTranslator(self._simulation.manager, self._entity_ids)
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
        return build_observation(self._require_simulation().manager, self._tick, self._entity_ids)

    def fog_state(self, team: TeamColor | str | None = None) -> tuple[tuple[int, ...], ...]:
        """Return a per-team fog visibility grid as an immutable row-major grid.

        This is an opt-in observation variant kept out of the default snapshot so
        many-instance training stays cheap. A fresh ``FogOfWar`` is computed from
        the requested team's entities, leaving the renderer's own fog untouched.
        Cells are ``0`` unexplored, ``1`` explored, ``2`` visible.
        """
        manager = self._require_simulation().manager
        team_enum = self._normalize_team(team) or manager.current_team
        group = manager.teams.get(team_enum)
        fog = FogOfWar(manager.map_width, manager.map_height)
        fog.update(manager.state.entities_for_team(team_enum) if group is not None else [])
        return tuple(tuple(row) for row in fog.grid)

    def available_actions(self) -> tuple[ActionSpec, ...]:
        """Return currently legal action families."""
        return tuple(spec for spec in self.action_mask() if spec.enabled)

    def action_mask(self, team: TeamColor | str | None = None) -> tuple[ActionSpec, ...]:
        """Return legal/illegal action families with denial reasons."""
        manager = self._require_simulation().manager
        requested_team = self._normalize_team(team)
        teams = tuple(
            candidate_team
            for candidate_team in manager.teams
            if requested_team is None or candidate_team == requested_team
        )

        specs: list[ActionSpec] = [ActionSpec("no_op")]
        for candidate_team in teams:
            specs.extend(self._team_action_specs(candidate_team))
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
            self._action_translator = None

    def _apply_action(self, action: Action) -> None:
        self._require_action_translator().apply(action)

    def _require_action_translator(self) -> ActionTranslator:
        if self._action_translator is None:
            raise RuntimeError("The environment is closed. Call reset() before using it again.")
        return self._action_translator

    def _require_simulation(self) -> HeadlessSimulation:
        if self._simulation is None:
            raise RuntimeError("The environment is closed. Call reset() before using it again.")
        return self._simulation

    @staticmethod
    def _frames_for(action: Action) -> int:
        return action.frames

    def _team_action_specs(self, team: TeamColor) -> tuple[ActionSpec, ...]:
        manager = self._require_simulation().manager
        units = manager.orders.units_for_team(team)
        bases = manager.orders.bases_for_team(team)
        production_buildings = manager.orders.production_buildings_for_team(team)
        peasants = [unit for unit in units if isinstance(unit, Peasant)]
        carrying_peasants = [unit for unit in peasants if unit.carry_wood > 0 or unit.carry_gold > 0]
        resources = [
            resource
            for resource in (*manager.state.resources_by_content("wood"), *manager.state.resources_by_content("gold"))
            if resource.amount > 0
        ]
        hostile_targets = [
            entity
            for entity in manager.all_entities
            if isinstance(entity, (Unit, Building)) and entity.team != team and entity.life > 0
        ]

        team_name = team.value
        build_specs = tuple(
            ActionSpec(
                "build",
                team_name,
                "producer_id",
                enabled=can_build,
                reason=reason,
                unit_type=unit_type,
            )
            for unit_type in CONTENT.units
            for can_build, reason in (self._can_build_unit(team, production_buildings, unit_type),)
        )
        construct_specs = tuple(
            ActionSpec(
                "construct",
                team_name,
                "world_point",
                enabled=can_construct,
                reason=reason,
                building_type=building_type,
            )
            for building_type in manager.construction.supported_building_types()
            for can_construct, reason in (manager.construction.can_team_construct(team, building_type),)
        )
        unfinished_buildings = manager.construction.unfinished_buildings_for_team(team)
        can_cancel = any(manager.production.queue_for(producer) for producer in production_buildings)
        return (
            ActionSpec("move", team_name, "world_point", enabled=bool(units), reason=None if units else "no_units"),
            ActionSpec(
                "attack_move",
                team_name,
                "world_point",
                enabled=bool(units),
                reason=None if units else "no_units",
            ),
            ActionSpec(
                "patrol",
                team_name,
                "world_point",
                enabled=bool(units),
                reason=None if units else "no_units",
            ),
            ActionSpec("stop", team_name, "unit_ids", enabled=bool(units), reason=None if units else "no_units"),
            ActionSpec("hold", team_name, "unit_ids", enabled=bool(units), reason=None if units else "no_units"),
            ActionSpec(
                "attack",
                team_name,
                "entity_id",
                enabled=bool(units and hostile_targets),
                reason=None if units and hostile_targets else "no_units_or_targets",
            ),
            ActionSpec(
                "gather",
                team_name,
                "resource_id",
                enabled=bool(peasants and resources),
                reason=None if peasants and resources else "no_peasants_or_resources",
            ),
            ActionSpec(
                "deposit",
                team_name,
                "base_id",
                enabled=bool(carrying_peasants and bases),
                reason=None if carrying_peasants and bases else "no_cargo_or_base",
            ),
            ActionSpec(
                "return_cargo",
                team_name,
                "base_id",
                enabled=bool(carrying_peasants and bases),
                reason=None if carrying_peasants and bases else "no_cargo_or_base",
            ),
            *build_specs,
            *construct_specs,
            ActionSpec(
                "cancel_construction",
                team_name,
                "building_id",
                enabled=bool(unfinished_buildings),
                reason=None if unfinished_buildings else "no_unfinished_building",
            ),
            ActionSpec(
                "cancel_production",
                team_name,
                "producer_id",
                enabled=can_cancel,
                reason=None if can_cancel else "empty_queue",
            ),
            ActionSpec(
                "select",
                team_name,
                "entity_ids",
                enabled=bool(units or production_buildings),
                reason=None if units or production_buildings else "no_entities",
            ),
        )

    def _can_build_unit(
        self,
        team: TeamColor,
        producers: list[Building],
        unit_type: str,
    ) -> tuple[bool, str | None]:
        if not producers:
            return False, "no_producer"
        last_reason: str | None = None
        for producer in producers:
            if producer.team != team:
                continue
            can_build, reason = self._require_simulation().manager.production.can_enqueue_unit(producer, unit_type)
            if can_build:
                return True, None
            last_reason = reason
        return False, last_reason

    @staticmethod
    def _normalize_team(team: TeamColor | str | None) -> TeamColor | None:
        if team is None or isinstance(team, TeamColor):
            return team
        return TeamColor(team)

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
