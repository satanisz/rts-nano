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
    BuildAction,
    DepositAction,
    GatherAction,
    MoveAction,
    NoOpAction,
    SelectAction,
    WorldPoint,
)
from rts_nano.actions import (
    ActionKind as ActionKind,
)
from rts_nano.game.observations import (
    EntityId,
    EntityIdRegistry,
    EntitySnapshot,
    Observation,
    TeamSnapshot,
    build_observation,
)
from rts_nano.headless import HeadlessSimulation

if TYPE_CHECKING:
    from rts_nano.map_schema import MapSettings

DEFAULT_MAP_ID = "map_settings_01.json"
MAPS_DIR = Path(__file__).resolve().parent / "maps"
__all__ = [
    "Action",
    "ActionSpec",
    "AttackAction",
    "BuildAction",
    "DepositAction",
    "EntityId",
    "EntitySnapshot",
    "GatherAction",
    "MoveAction",
    "NoOpAction",
    "Observation",
    "RtsNanoEnv",
    "SelectAction",
    "StepResult",
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
