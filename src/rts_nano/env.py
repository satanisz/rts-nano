"""Public headless environment facade for AI and RL integrations."""

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from rts_nano.action_translation import ActionTranslator
from rts_nano.actions import (
    Action,
    ActionSpec,
    AssistConstructionAction,
    AttackAction,
    AttackMoveAction,
    BuildAction,
    BuildingType,
    CancelActivityAction,
    CancelConstructionAction,
    CancelProductionAction,
    CastAction,
    ConstructAction,
    DepositAction,
    GatherAction,
    HoldAction,
    MoveAction,
    NoOpAction,
    PatrolAction,
    RepairAction,
    ResearchAction,
    ReturnCargoAction,
    SelectAction,
    SetRallyAction,
    StopAction,
    WorldPoint,
)
from rts_nano.actions import (
    ActionKind as ActionKind,
)
from rts_nano.content import CONTENT
from rts_nano.game.fog import FogOfWar
from rts_nano.game.observations import (
    AbilitySnapshot,
    ActivitySnapshot,
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
from rts_nano.simulation.entities.units import CasterUnit, Peasant

if TYPE_CHECKING:
    from collections.abc import Mapping

    from rts_nano.map_schema import MapSettings

DEFAULT_MAP_ID = "map_settings_01.json"
DEFAULT_MAX_EPISODE_FRAMES = 36_000
MAPS_DIR = Path(__file__).resolve().parent / "maps"
__all__ = [
    "Action",
    "ActionSpec",
    "ActionOutcome",
    "AbilitySnapshot",
    "ActivitySnapshot",
    "AssistConstructionAction",
    "AttackMoveAction",
    "AttackAction",
    "BuildingType",
    "BuildAction",
    "CancelConstructionAction",
    "CancelActivityAction",
    "CancelProductionAction",
    "CastAction",
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
    "RepairAction",
    "ResearchAction",
    "ReturnCargoAction",
    "RtsNanoEnv",
    "JointStepResult",
    "EpisodeEndReason",
    "SelectAction",
    "SetRallyAction",
    "StepResult",
    "StopAction",
    "TeamSnapshot",
    "WorldPoint",
]


class EpisodeEndReason(StrEnum):
    """Stable reasons why an RL episode stopped advancing."""

    GAME_RESULT = "game_result"
    TIME_LIMIT = "time_limit"


@dataclass(frozen=True, slots=True)
class ActionOutcome:
    """Result of validating and applying one command from a joint batch."""

    index: int
    team: str
    kind: str
    accepted: bool
    affected_count: int = 0
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class JointStepResult:
    """Multi-team result returned by the future simultaneous step contract."""

    observation: Observation
    rewards: dict[str, float]
    terminated: bool
    truncated: bool
    action_outcomes: tuple[ActionOutcome, ...]
    info: dict[str, object]

    @property
    def done(self) -> bool:
        """Return whether the caller must reset before another step."""
        return self.terminated or self.truncated


@dataclass(frozen=True, slots=True)
class StepResult:
    """Result returned by one environment step."""

    observation: Observation
    reward: float
    done: bool
    info: dict[str, object]
    terminated: bool = False
    truncated: bool = False


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
        reward_fns: Mapping[TeamColor | str, RewardFunction] | None = None,
        max_episode_frames: int | None = DEFAULT_MAX_EPISODE_FRAMES,
    ) -> None:
        """Initialize an environment and load the initial simulation."""
        self._map_id = map_id
        self._settings = settings
        self._frame_skip = max(1, frame_skip)
        if reward_fn is not None and reward_fns is not None:
            raise ValueError("reward_fn and reward_fns are mutually exclusive")
        self._reward_fn = reward_fn
        self._reward_fns = self._normalize_reward_fns(reward_fns)
        if max_episode_frames is not None and max_episode_frames <= 0:
            raise ValueError("max_episode_frames must be positive or None")
        self._max_episode_frames = max_episode_frames
        self._seed: int | None = None
        self._simulation: HeadlessSimulation | None = None
        self._entity_ids = EntityIdRegistry()
        self._action_translator: ActionTranslator | None = None
        self._tick = 0
        self._episode_id = 0
        self._decision_count = 0
        self._terminated = False
        self._truncated = False
        self._end_reason: EpisodeEndReason | None = None
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
        self._episode_id += 1
        self._decision_count = 0
        self._terminated = False
        self._truncated = False
        self._end_reason = None
        reset_reward = getattr(self._reward_fn, "reset", None)
        if callable(reset_reward):
            reset_reward()
        for reward in self._reward_fns.values():
            reset_team_reward = getattr(reward, "reset", None)
            if callable(reset_team_reward):
                reset_team_reward()

        if self._settings is not None:
            settings_copy = copy.deepcopy(self._settings)
            self._simulation = HeadlessSimulation.from_settings(settings_copy)
        else:
            self._simulation = HeadlessSimulation.from_map_file(self._resolve_map_path(self._map_id))
        self._action_translator = ActionTranslator(self._simulation.manager, self._entity_ids)
        return self.observe()

    def step(self, action: Action) -> StepResult:
        """Apply an action, advance the simulation, and return the step result."""
        self._ensure_can_step()
        simulation = self._require_simulation()
        requested_frames = max(0, self._frames_for(action) * self._frame_skip)
        remaining = self._remaining_episode_frames()
        frames = requested_frames if remaining is None else min(requested_frames, remaining)
        self._apply_action(action)
        advanced = simulation.step(frames)
        self._tick += advanced
        self._decision_count += 1
        self._update_episode_end()
        observation = self.observe()
        return StepResult(
            observation=observation,
            reward=self.reward(observation),
            done=self.is_done(),
            info=self._step_info(advanced, requested_frames),
            terminated=self._terminated,
            truncated=self._truncated,
        )

    def observe(self) -> Observation:
        """Return a serializable snapshot of the current simulation state."""
        return build_observation(self._require_simulation().manager, self._tick, self._entity_ids)

    def step_joint(
        self,
        actions: Mapping[TeamColor | str, tuple[Action, ...]],
    ) -> JointStepResult:
        """Apply both teams' prevalidated batches, then advance simulation exactly once."""
        from rts_nano.joint_actions import prepare_joint_actions

        self._ensure_can_step()
        simulation = self._require_simulation()
        translator = self._require_action_translator()
        prepared = prepare_joint_actions(simulation.manager, translator, actions)
        outcomes: list[ActionOutcome] = []
        for item in prepared:
            affected = 0
            if item.accepted:
                try:
                    affected = translator.apply(item.action)
                except KeyError, ValueError:
                    item.accepted = False
                    item.reason = "invalid_entity"
                if item.accepted and not isinstance(item.action, NoOpAction) and affected <= 0:
                    item.accepted = False
                    item.reason = "not_applied"
            outcomes.append(
                ActionOutcome(
                    item.index,
                    item.team.value,
                    item.kind,
                    item.accepted,
                    affected,
                    item.reason,
                )
            )
        requested_frames = self._frame_skip
        remaining = self._remaining_episode_frames()
        frames = requested_frames if remaining is None else min(requested_frames, remaining)
        advanced = simulation.step(frames)
        self._tick += advanced
        self._decision_count += 1
        self._update_episode_end()
        observation = self.observe()
        rewards = {
            team.value: self._reward_fns[team](observation) if team in self._reward_fns else 0.0
            for team in (TeamColor.BLUE, TeamColor.RED)
        }
        return JointStepResult(
            observation=observation,
            rewards=rewards,
            terminated=self._terminated,
            truncated=self._truncated,
            action_outcomes=tuple(outcomes),
            info=self._step_info(advanced, requested_frames),
        )

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
        return self._terminated or self._truncated

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

    def _ensure_can_step(self) -> None:
        self._require_simulation()
        if self.is_done():
            raise RuntimeError("Episode is complete. Call reset() before stepping again.")

    def _remaining_episode_frames(self) -> int | None:
        if self._max_episode_frames is None:
            return None
        return max(0, self._max_episode_frames - self._tick)

    def _update_episode_end(self) -> None:
        if self._require_simulation().manager.game_over_message is not None:
            self._terminated = True
            self._end_reason = EpisodeEndReason.GAME_RESULT
        elif self._max_episode_frames is not None and self._tick >= self._max_episode_frames:
            self._truncated = True
            self._end_reason = EpisodeEndReason.TIME_LIMIT

    def _step_info(self, advanced_frames: int, requested_frames: int) -> dict[str, object]:
        manager = self._require_simulation().manager
        return {
            "tick": self._tick,
            "frames": advanced_frames,
            "requested_frames": requested_frames,
            "decision_count": self._decision_count,
            "episode_id": self._episode_id,
            "seed": self._seed,
            "game_result": manager.game_over_message,
            "end_reason": self._end_reason.value if self._end_reason is not None else None,
        }

    @staticmethod
    def _normalize_reward_fns(
        reward_fns: Mapping[TeamColor | str, RewardFunction] | None,
    ) -> dict[TeamColor, RewardFunction]:
        normalized: dict[TeamColor, RewardFunction] = {}
        for key, reward in (reward_fns or {}).items():
            try:
                team = key if isinstance(key, TeamColor) else TeamColor(key)
            except ValueError as exc:
                raise ValueError(f"Unknown reward team: {key}") from exc
            if team not in {TeamColor.BLUE, TeamColor.RED}:
                raise ValueError(f"Unsupported reward team: {team.value}")
            if team in normalized:
                raise ValueError(f"Duplicate reward team: {team.value}")
            normalized[team] = reward
        return normalized

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
        damaged_buildings = [
            building
            for building in manager.state.buildings_for_team(team)
            if not building.is_under_construction and 0 < building.life < building.max_life
        ]
        can_cancel = any(manager.production.queue_for(producer) for producer in production_buildings)
        cast_specs = tuple(
            ActionSpec(
                "cast",
                team_name,
                ability.target_kind.value,
                ability_id=str(ability.id),
                caster_id=self._entity_ids.id_for(caster),
            )
            for caster in units
            if isinstance(caster, CasterUnit)
            for ability in manager.abilities.available_abilities(caster)
        )
        research_specs = tuple(
            ActionSpec(
                "research",
                team_name,
                "producer_id",
                enabled=can_research,
                reason=reason,
                upgrade_id=upgrade_id,
            )
            for upgrade_id in CONTENT.upgrades
            for can_research, reason in (self._can_research(team, production_buildings, upgrade_id),)
        )
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
            *research_specs,
            *cast_specs,
            ActionSpec(
                "set_rally",
                team_name,
                "producer_id",
                enabled=bool(production_buildings),
                reason=None if production_buildings else "no_producer",
            ),
            ActionSpec(
                "repair",
                team_name,
                "building_id",
                enabled=bool(peasants and damaged_buildings),
                reason=None if peasants and damaged_buildings else "no_peasant_or_damaged_building",
            ),
            ActionSpec(
                "assist_construction",
                team_name,
                "building_id",
                enabled=bool(peasants and unfinished_buildings),
                reason=None if peasants and unfinished_buildings else "no_peasant_or_unfinished_building",
            ),
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
                "cancel_activity",
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

    def _can_research(
        self,
        team: TeamColor,
        producers: list[Building],
        upgrade_id: str,
    ) -> tuple[bool, str | None]:
        if not producers:
            return False, "no_producer"
        last_reason: str | None = None
        for producer in producers:
            if producer.team != team:
                continue
            can_research, reason = self._require_simulation().manager.can_research(producer, upgrade_id)
            if can_research:
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
