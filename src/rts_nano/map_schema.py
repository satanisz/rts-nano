"""Typed map-schema helpers shared by the game, editor, and validators.

Map files are JSON objects with four top-level sections:

* ``Blue`` and ``Red`` contain spawn coordinates for team-owned entities.
* ``Resources`` contains neutral resource coordinates.
* ``Terrain`` contains map dimensions plus terrain/decorative layers.

The canonical terrain format stores ``high_ground`` and ``water`` as grouped
rectangle shapes. A shape is a list of one or more rectangles, so both a single
rectangle and an L-shaped joined region use the same outer structure:

``"high_ground": [[[x, y, width, height]]]``

``"water": [[[x, y, width, height], [x2, y2, width2, height2]]]``

This module deliberately uses ``TypedDict`` rather than dataclasses because the
runtime still mutates JSON-like lists directly in the map editor. The helpers
provide enough typing and validation for future agents to understand the schema
without forcing a full serialization rewrite.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, NotRequired, Required, TypedDict, cast

from rts_nano.content import CONTENT

if TYPE_CHECKING:
    from pathlib import Path

type Number = int | float
type Coordinate = list[int]
type RectPayload = list[int]
type RectGroupPayload = list[RectPayload]


class TeamSettings(TypedDict, total=False):
    """Serialized spawn lists for one controllable team.

    Entity names are faction-aware: ``peasant``, ``base`` and ``house`` are
    shared, while military units and tech buildings belong to a faction (AEGIS
    on Blue, RUST on Red). The validator accepts any name in
    :data:`TEAM_ENTITY_NAMES`, regardless of which team it appears under.
    """

    faction_id: Required[str]
    # Shared
    peasant: list[Coordinate]
    base: list[Coordinate]
    house: list[Coordinate]
    # AEGIS
    marksman: list[Coordinate]
    guardian: list[Coordinate]
    arclight: list[Coordinate]
    arsenal: list[Coordinate]
    spire: list[Coordinate]
    bastion: list[Coordinate]
    # RUST
    ripper: list[Coordinate]
    spitter: list[Coordinate]
    brute: list[Coordinate]
    pit: list[Coordinate]
    chem_vat: list[Coordinate]
    spiker: list[Coordinate]


# Entity names accepted in a team's spawn section.
TEAM_ENTITY_NAMES: frozenset[str] = frozenset((*CONTENT.units, *CONTENT.buildings))


class ResourceSettings(TypedDict, total=False):
    """Serialized neutral resource lists."""

    wood: list[Coordinate]
    gold: list[Coordinate]


class TerrainSettings(TypedDict):
    """Serialized terrain section.

    ``high_ground`` and ``water`` use grouped rectangle payloads. ``ramps`` stay
    flat because every ramp rectangle is an independent connector. ``rocks`` and
    ``grass`` are point-radius payloads represented as ``[x, y, radius]``.
    """

    width: int
    height: int
    high_ground: list[RectGroupPayload]
    ramps: list[RectPayload]
    water: list[RectGroupPayload]
    rocks: list[list[int]]
    grass: list[list[int]]


class MapSettings(TypedDict):
    """Complete serialized map payload."""

    schema_version: int
    Blue: TeamSettings
    Red: TeamSettings
    Resources: ResourceSettings
    Terrain: TerrainSettings
    Grey: NotRequired[TeamSettings]


def load_map_settings(path: Path) -> MapSettings:
    """Load and validate a map JSON file.

    Args:
        path: Path to the JSON file.

    Returns:
        Parsed map settings typed as ``MapSettings``.

    Raises:
        ValueError: If the file does not match the canonical map schema.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    with path.open(encoding="utf-8") as map_file:
        payload = json.load(map_file)

    errors = validate_map_settings(payload)
    if errors:
        formatted_errors = "\n".join(f"- {error}" for error in errors)
        raise ValueError(f"Invalid map settings in {path}:\n{formatted_errors}")
    return cast("MapSettings", payload)


def validate_map_settings(payload: object) -> list[str]:
    """Return schema validation errors for a loaded map payload."""
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["Map root must be a JSON object."]

    root = cast("dict[object, object]", payload)
    if root.get("schema_version") != 2:
        errors.append("schema_version must be 2.")
    _validate_team(root, "Blue", errors)
    _validate_team(root, "Red", errors)
    _validate_resources(root, errors)
    _validate_terrain(root, errors)
    return errors


def normalize_grouped_terrain(settings: MapSettings) -> None:
    """Normalize high-ground and water terrain to grouped rectangle payloads.

    This helper is intentionally permissive and accepts legacy flat rectangle
    entries. The editor calls similar logic before saving; this function is
    useful for tests or external tools that want to migrate in-memory payloads.
    """
    terrain = settings["Terrain"]
    terrain["high_ground"] = [_rect_group_from_payload(payload) for payload in terrain.get("high_ground", [])]
    terrain["water"] = [_rect_group_from_payload(payload) for payload in terrain.get("water", [])]


def _validate_team(payload: dict[object, object], key: str, errors: list[str]) -> None:
    team = payload.get(key)
    if not isinstance(team, dict):
        errors.append(f"{key} must be an object.")
        return
    team_payload = cast("dict[object, object]", team)
    faction_id = team_payload.get("faction_id")
    if not isinstance(faction_id, str) or faction_id not in CONTENT.factions:
        errors.append(f"{key}.faction_id must name a known faction.")
    available_content = (
        set(CONTENT.units_for_faction(faction_id)) | set(CONTENT.buildings_for_faction(faction_id))
        if isinstance(faction_id, str) and faction_id in CONTENT.factions
        else set()
    )
    for entity_name, coords in team_payload.items():
        if entity_name == "faction_id":
            continue
        if entity_name not in TEAM_ENTITY_NAMES:
            errors.append(f"{key}.{entity_name} is not a known entity type.")
            continue
        if entity_name not in available_content:
            errors.append(f"{key}.{entity_name} is not available to faction {faction_id}.")
            continue
        _validate_coordinate_list(coords, f"{key}.{entity_name}", errors)


def _validate_resources(payload: dict[object, object], errors: list[str]) -> None:
    resources = payload.get("Resources")
    if not isinstance(resources, dict):
        errors.append("Resources must be an object.")
        return
    for resource_name, coords in resources.items():
        if resource_name not in CONTENT.resources:
            errors.append(f"Resources.{resource_name} is not a known resource type.")
            continue
        _validate_coordinate_list(coords, f"Resources.{resource_name}", errors)


def _validate_terrain(payload: dict[object, object], errors: list[str]) -> None:
    terrain = payload.get("Terrain")
    if not isinstance(terrain, dict):
        errors.append("Terrain must be an object.")
        return
    terrain_payload = cast("dict[object, object]", terrain)

    for dimension in ("width", "height"):
        value = terrain_payload.get(dimension)
        if not isinstance(value, int) or value <= 0:
            errors.append(f"Terrain.{dimension} must be a positive integer.")

    _validate_grouped_rect_list(terrain_payload.get("high_ground"), "Terrain.high_ground", errors)
    _validate_grouped_rect_list(terrain_payload.get("water"), "Terrain.water", errors)
    _validate_rect_list(terrain_payload.get("ramps"), "Terrain.ramps", errors)
    _validate_point_radius_list(terrain_payload.get("rocks"), "Terrain.rocks", errors)
    _validate_point_radius_list(terrain_payload.get("grass"), "Terrain.grass", errors)


def _validate_coordinate_list(payload: object, label: str, errors: list[str]) -> None:
    if not isinstance(payload, list):
        errors.append(f"{label} must be a list of [x, y] coordinates.")
        return
    for index, item in enumerate(payload):
        if not _is_coordinate(item):
            errors.append(f"{label}[{index}] must be [x, y].")


def _validate_grouped_rect_list(payload: object, label: str, errors: list[str]) -> None:
    if not isinstance(payload, list):
        errors.append(f"{label} must be a list of rectangle groups.")
        return
    for group_index, group in enumerate(payload):
        if not isinstance(group, list) or not group:
            errors.append(f"{label}[{group_index}] must be a non-empty rectangle group.")
            continue
        for rect_index, rect in enumerate(group):
            if not _is_rect_payload(rect):
                errors.append(f"{label}[{group_index}][{rect_index}] must be [x, y, width, height].")


def _validate_rect_list(payload: object, label: str, errors: list[str]) -> None:
    if not isinstance(payload, list):
        errors.append(f"{label} must be a list of [x, y, width, height] rectangles.")
        return
    for index, item in enumerate(payload):
        if not _is_rect_payload(item):
            errors.append(f"{label}[{index}] must be [x, y, width, height].")


def _validate_point_radius_list(payload: object, label: str, errors: list[str]) -> None:
    if not isinstance(payload, list):
        errors.append(f"{label} must be a list of [x, y, radius] payloads.")
        return
    for index, item in enumerate(payload):
        if not _is_point_radius(item):
            errors.append(f"{label}[{index}] must be [x, y, radius].")


def _rect_group_from_payload(payload: object) -> RectGroupPayload:
    if _is_rect_payload(payload):
        return [cast("RectPayload", payload)]
    if isinstance(payload, list):
        return [cast("RectPayload", rect) for rect in payload if _is_rect_payload(rect)]
    return []


def _is_coordinate(payload: object) -> bool:
    return isinstance(payload, list) and len(payload) == 2 and all(isinstance(value, (int, float)) for value in payload)


def _is_rect_payload(payload: object) -> bool:
    if not isinstance(payload, list) or len(payload) != 4:
        return False
    x, y, width, height = payload
    if not all(isinstance(value, int) for value in (x, y, width, height)):
        return False
    return cast("int", width) > 0 and cast("int", height) > 0


def _is_point_radius(payload: object) -> bool:
    if not isinstance(payload, list) or len(payload) != 3:
        return False
    x, y, radius = payload
    if not all(isinstance(value, int) for value in (x, y, radius)):
        return False
    return cast("int", radius) > 0
