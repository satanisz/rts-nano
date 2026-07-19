"""Tests for presentation-independent simulation geometry."""

from __future__ import annotations

import pytest

from rts_nano.simulation.geometry import Rect


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        (((0, 0), (200, 200)), ((20.0, 20.0), (99.0, 99.0))),
        (((20, 30), (50, 60)), ((20.0, 30.0), (50.0, 60.0))),
        (((0, 40), (200, 40)), ((10.0, 40.0), (109.0, 40.0))),
        (((0, 0), (5, 5)), None),
        (((0, 0), (33, 111)), ((10.0, 36.0), (29.0, 99.0))),
    ],
)
def test_rect_clipline_preserves_integer_sdl_semantics(
    line: tuple[tuple[float, float], tuple[float, float]],
    expected: tuple[tuple[float, float], tuple[float, float]] | None,
) -> None:
    """Line clipping keeps the former inclusive/exclusive edge behavior."""
    assert Rect(10, 20, 100, 80).clipline(*line) == expected


def test_rect_point_and_inflate_preserve_edge_semantics() -> None:
    """Right/bottom edges are excluded and inflation retains the center."""
    rect = Rect(10, 20, 100, 80)

    assert rect.collidepoint((10, 20))
    assert rect.collidepoint((109, 99))
    assert not rect.collidepoint((110, 100))
    assert rect.inflate(11, 13) == Rect(5, 14, 111, 93)
