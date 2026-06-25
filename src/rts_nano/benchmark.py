"""Headless performance and batch helpers for training-scale experiments.

These utilities never open a window or draw frames. ``measure_steps_per_second``
reports single-instance throughput; ``run_batch`` advances many environments in
one process and collects per-environment reward totals. Both are deliberately
dependency-light so they can run in CI and on machines without a GPU.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from rts_nano.actions import NoOpAction
from rts_nano.env import RtsNanoEnv

if TYPE_CHECKING:
    from pathlib import Path

    from rts_nano.map_schema import MapSettings
    from rts_nano.rewards import RewardFunction


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    """Throughput measured for a single headless environment."""

    steps: int
    elapsed_seconds: float

    @property
    def steps_per_second(self) -> float:
        """Return measured steps per second, or 0.0 for a zero-length run."""
        if self.elapsed_seconds <= 0:
            return 0.0
        return self.steps / self.elapsed_seconds


def measure_steps_per_second(
    *,
    steps: int = 2000,
    frames_per_step: int = 1,
    map_id: str | Path | None = None,
    settings: MapSettings | None = None,
) -> BenchmarkResult:
    """Advance one headless environment and report its step throughput."""
    env = RtsNanoEnv(map_id=map_id, settings=settings)
    action = NoOpAction(frames=frames_per_step)
    start = time.perf_counter()
    for _ in range(max(0, steps)):
        if env.step(action).done:
            env.reset()
    elapsed = time.perf_counter() - start
    env.close()
    return BenchmarkResult(steps=max(0, steps), elapsed_seconds=elapsed)


def run_batch(
    *,
    num_envs: int,
    steps: int,
    settings: MapSettings | None = None,
    map_id: str | Path | None = None,
    reward_fn: RewardFunction | None = None,
) -> list[float]:
    """Advance ``num_envs`` environments for ``steps`` ticks and sum rewards.

    Environments are never reset or closed mid-run so the shared headless pygame
    state stays valid for every instance; a terminal environment simply stops
    accumulating reward. All environments are closed once the run completes.
    """
    envs = [RtsNanoEnv(map_id=map_id, settings=settings, reward_fn=reward_fn) for _ in range(max(0, num_envs))]
    totals = [0.0] * len(envs)
    done_flags = [False] * len(envs)
    action = NoOpAction(frames=1)

    for _ in range(max(0, steps)):
        for index, env in enumerate(envs):
            if done_flags[index]:
                continue
            result = env.step(action)
            totals[index] += result.reward
            done_flags[index] = result.done

    for env in envs:
        env.close()
    return totals


def main() -> None:
    """Print single-instance throughput on the default map."""
    result = measure_steps_per_second(steps=2000)
    print(f"steps={result.steps} elapsed={result.elapsed_seconds:.3f}s steps_per_second={result.steps_per_second:.0f}")


if __name__ == "__main__":
    main()
