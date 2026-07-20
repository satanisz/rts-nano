"""Composable reward functions for ``RtsNanoEnv`` experiments.

The environment accepts any ``Callable[[Observation], float]`` as ``reward_fn``.
These builders return such callables with configurable weights so experiments can
define task-specific goals without changing the game rules. Built-in delta rewards
provide ``reset()`` so one environment can safely reuse them across episodes.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from rts_nano.game.observations import Observation, TeamSnapshot

type RewardFunction = Callable[[Observation], float]


@dataclass(slots=True)
class _DeltaReward:
    """Resettable delta reward used safely across environment episodes."""

    measure: Callable[[Observation], float]
    previous: float | None = None

    def __call__(self, observation: Observation) -> float:
        current = self.measure(observation)
        last = self.previous
        self.previous = current
        return 0.0 if last is None else current - last

    def reset(self) -> None:
        self.previous = None


@dataclass(slots=True)
class _CombinedReward:
    """Weighted reward composition with reset propagation."""

    rewards: list[RewardFunction]
    weights: list[float]

    def __call__(self, observation: Observation) -> float:
        return sum(weight * reward(observation) for reward, weight in zip(self.rewards, self.weights, strict=True))

    def reset(self) -> None:
        for reward in self.rewards:
            reset = getattr(reward, "reset", None)
            if callable(reset):
                reset()


def _team(observation: Observation, team: str) -> TeamSnapshot | None:
    return next((snapshot for snapshot in observation.teams if snapshot.team == team), None)


def win_loss_reward(team: str, *, win: float = 1.0, loss: float = -1.0, draw: float = 0.0) -> RewardFunction:
    """Reward a terminal win/loss/draw for ``team`` and zero otherwise."""

    def reward(observation: Observation) -> float:
        if observation.game_over is None:
            return 0.0
        if observation.game_over == f"Team {team} wins":
            return win
        if observation.game_over == "Draw":
            return draw
        return loss

    return reward


def resource_gain_reward(team: str, *, wood_weight: float = 1.0, gold_weight: float = 1.0) -> RewardFunction:
    """Reward the per-step increase in a team's banked resources."""

    def measure(observation: Observation) -> float:
        snapshot = _team(observation, team)
        if snapshot is None:
            return 0.0
        return snapshot.wood * wood_weight + snapshot.gold * gold_weight

    return _DeltaReward(measure)


def enemy_losses_reward(team: str, *, unit_weight: float = 1.0, building_weight: float = 2.0) -> RewardFunction:
    """Reward reductions in rival unit and building counts since the last step."""

    def measure(observation: Observation) -> float:
        rivals = [snapshot for snapshot in observation.teams if snapshot.team != team]
        return -sum(snapshot.units * unit_weight + snapshot.buildings * building_weight for snapshot in rivals)

    return _DeltaReward(measure)


def combine(rewards: Sequence[RewardFunction], *, weights: Sequence[float] | None = None) -> RewardFunction:
    """Combine reward functions into a single weighted-sum reward function."""
    reward_list = list(rewards)
    weight_list = list(weights) if weights is not None else [1.0] * len(reward_list)
    if len(weight_list) != len(reward_list):
        raise ValueError("weights must match the number of reward functions")

    return _CombinedReward(reward_list, weight_list)
