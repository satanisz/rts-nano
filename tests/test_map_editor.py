"""Tests for map editor data operations."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pygame

from rts_nano.map_editor import MapEditor

if TYPE_CHECKING:
    from pathlib import Path


def _write_map(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "Blue": {"base": [[100, 100]]},
                "Red": {"base": []},
                "Resources": {"wood": [[200, 200]], "cristal": []},
                "Terrain": {
                    "width": 500,
                    "height": 500,
                    "high_ground": [[[10, 10, 50, 50]]],
                    "ramps": [],
                    "water": [[[100, 100, 40, 40]]],
                    "rocks": [],
                    "grass": [],
                },
            }
        ),
        encoding="utf-8",
    )


def test_editor_merges_high_ground_and_water_as_grouped_shapes(tmp_path: Path) -> None:
    """Touching high/water rectangles become nested grouped shapes."""
    path = tmp_path / "map.json"
    _write_map(path)
    editor = MapEditor(path)

    editor._add_rect_item("high_ground", pygame.Rect(59, 10, 40, 50))
    editor._add_rect_item("water", pygame.Rect(139, 100, 40, 40))

    assert editor.terrain_settings["high_ground"] == [[[59, 10, 40, 50], [10, 10, 50, 50]]]
    assert editor.terrain_settings["water"] == [[[139, 100, 40, 40], [100, 100, 40, 40]]]


def test_editor_erase_and_flatten_remove_expected_payloads(tmp_path: Path) -> None:
    """Erase removes assets while flatten removes terrain only."""
    path = tmp_path / "map.json"
    _write_map(path)
    editor = MapEditor(path)

    editor._erase_area_or_point(pygame.Rect(0, 0, 0, 0), (200, 200))
    assert editor.settings["Resources"]["wood"] == []

    editor._flatten_area_or_point(pygame.Rect(0, 0, 80, 80), (0, 0))
    assert editor.terrain_settings["high_ground"] == []
    assert editor.settings["Blue"]["base"] == [[100, 100]]


def test_create_new_map_writes_blank_schema(tmp_path: Path) -> None:
    """New maps are written with the canonical empty schema."""
    source_path = tmp_path / "source.json"
    _write_map(source_path)
    editor = MapEditor(source_path)
    editor.create_new_map(tmp_path / "new.json", width=123, height=456)
    payload = json.loads((tmp_path / "new.json").read_text(encoding="utf-8"))

    assert payload["Terrain"]["width"] == 123
    assert payload["Terrain"]["height"] == 456
    assert payload["Terrain"]["high_ground"] == []
    assert payload["Blue"]["barracks"] == []
    assert payload["Red"]["barracks"] == []
