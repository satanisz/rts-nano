"""Tests for map schema typing and validation."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from rts_nano.map_schema import load_map_settings, validate_map_settings
from rts_nano.validate_map import validate_map_file

if TYPE_CHECKING:
    from pathlib import Path


def _valid_payload() -> dict[str, object]:
    return {
        "Blue": {"base": [[10, 10]], "barracks": [[60, 60]], "peasant": []},
        "Red": {"base": [[100, 100]], "barracks": []},
        "Resources": {"wood": [[20, 20]], "cristal": []},
        "Terrain": {
            "width": 500,
            "height": 400,
            "high_ground": [[[10, 10, 50, 50]]],
            "water": [[[100, 100, 30, 30]]],
            "ramps": [[50, 50, 20, 20]],
            "rocks": [[200, 200, 8]],
            "grass": [[250, 250, 6]],
        },
    }


def test_validate_map_settings_accepts_canonical_payload() -> None:
    """The canonical grouped terrain schema validates."""
    assert validate_map_settings(_valid_payload()) == []


def test_validate_map_settings_rejects_flat_high_ground() -> None:
    """Flat high-ground rectangles are no longer canonical schema."""
    payload = _valid_payload()
    terrain = payload["Terrain"]
    assert isinstance(terrain, dict)
    terrain["high_ground"] = [[10, 10, 50, 50]]

    errors = validate_map_settings(payload)

    assert any("Terrain.high_ground" in error for error in errors)


def test_load_map_settings_and_cli_validator(tmp_path: Path) -> None:
    """The loader returns valid maps and CLI helper reports errors."""
    valid_path = tmp_path / "valid.json"
    invalid_path = tmp_path / "invalid.json"
    valid_path.write_text(json.dumps(_valid_payload()), encoding="utf-8")
    invalid_path.write_text("{", encoding="utf-8")

    assert load_map_settings(valid_path)["Terrain"]["width"] == 500
    assert validate_map_file(valid_path) == []
    assert validate_map_file(invalid_path)
