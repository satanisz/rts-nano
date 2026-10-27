"""Immutable match rules shared by windowed and headless gameplay."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_MATCH_FRAMES = 36_000


@dataclass(frozen=True, slots=True)
class MatchRules:
    """Eliminate opposing forces, or draw when the simulation-time limit expires."""

    max_frames: int | None = DEFAULT_MATCH_FRAMES

    def __post_init__(self) -> None:
        """Reject invalid limits; None explicitly selects unbounded elimination."""
        if self.max_frames is not None and (
            isinstance(self.max_frames, bool) or not isinstance(self.max_frames, int) or self.max_frames <= 0
        ):
            raise ValueError("max_frames must be a positive integer or None")
