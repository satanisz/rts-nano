"""Semantic MapSpec v3 authoring format and deterministic runtime compiler.

MapSpec describes intent with named anchors, reusable placement patterns, and
mirror operations. Compilation expands that intent into the existing v2
``MapSettings`` payload consumed by the simulation. The compiler is pure and
does not depend on Pygame or presentation state.
"""

from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING, cast

from rts_nano.content import CONTENT

if TYPE_CHECKING:
    from collections.abc import Mapping

    from rts_nano.map_schema import MapSettings

type Point = tuple[int, int]
type JsonObject = dict[str, object]

SUPPORTED_PATTERNS = frozenset({"fixed_points", "ring", "arc", "line", "grid", "scatter"})
SUPPORTED_TERRAIN = frozenset({"high_ground", "water", "ramp", "rock", "grass"})


class MapSpecError(ValueError):
    """One precise authoring or compilation error with a semantic path."""


def compile_map_spec(payload: object) -> MapSettings:
    """Validate and deterministically expand one MapSpec v3 payload."""
    compiler = _MapSpecCompiler(_as_object(payload, "MapSpec root"))
    compiled = compiler.compile()
    errors = _semantic_errors(compiled)
    errors.extend(compiler.requirement_errors(compiled))
    if errors:
        raise MapSpecError("Invalid MapSpec:\n" + "\n".join(f"- {error}" for error in errors))
    return cast("MapSettings", compiled)


def validate_map_spec(payload: object) -> list[str]:
    """Return human/LLM-readable MapSpec v3 errors without raising."""
    try:
        compile_map_spec(payload)
    except (MapSpecError, TypeError, ValueError) as exc:
        message = str(exc)
        if message.startswith("Invalid MapSpec:\n"):
            return [line.removeprefix("- ") for line in message.splitlines()[1:]]
        return [message]
    return []


class _MapSpecCompiler:
    """Stateful single-pass compiler with stable named-reference resolution."""

    def __init__(self, spec: JsonObject) -> None:
        self.spec = spec
        self.width = 0
        self.height = 0
        self.symmetry_type = "none"
        self.symmetry_center: Point = (0, 0)
        self.anchors: dict[str, Point] = {}
        self.generated_placements: dict[str, list[tuple[str, str | None, Point]]] = {}
        self.generated_terrain: dict[str, tuple[str, object]] = {}

    def compile(self) -> JsonObject:
        if self.spec.get("schema_version") != 3:
            raise MapSpecError("schema_version must be 3")
        self._load_world()
        self._load_anchors()
        teams = self._compile_teams()
        resources: JsonObject = {resource_id: [] for resource_id in CONTENT.resources}
        self._compile_placements(teams, resources)
        terrain = self._compile_terrain()

        for required_team in ("Blue", "Red"):
            if required_team not in teams:
                raise MapSpecError(f"teams must define {required_team}")

        return {
            "schema_version": 2,
            **teams,
            "Resources": resources,
            "Terrain": terrain,
        }

    def requirement_errors(self, compiled: JsonObject) -> list[str]:
        """Evaluate optional author-stated strategic constraints."""
        from rts_nano.game.pathfinding import find_path
        from rts_nano.game.terrain import TerrainMap

        requirements = _as_object(self.spec.get("requirements", {}), "requirements")
        errors: list[str] = []
        resources = cast("JsonObject", compiled["Resources"])
        start_resources = _as_object(requirements.get("start_resources", {}), "requirements.start_resources")
        for resource_id, raw_rule in start_resources.items():
            if resource_id not in CONTENT.resources:
                errors.append(f"requirements.start_resources names unknown resource '{resource_id}'")
                continue
            rule = _as_object(raw_rule, f"requirements.start_resources.{resource_id}")
            max_distance = _positive_number(
                rule.get("max_distance"), f"requirements.start_resources.{resource_id}.max_distance"
            )
            min_nodes = _positive_int(rule.get("min_nodes"), f"requirements.start_resources.{resource_id}.min_nodes")
            resource_points = cast("list[list[int]]", resources.get(resource_id, []))
            for team_id in ("Blue", "Red"):
                team = cast("JsonObject", compiled[team_id])
                bases = cast("list[list[int]]", team.get("base", []))
                if not bases:
                    continue
                base = bases[0]
                nearby = sum(
                    math.hypot(base[0] - point[0], base[1] - point[1]) <= max_distance for point in resource_points
                )
                if nearby < min_nodes:
                    errors.append(
                        f"requirements.start_resources.{resource_id}: {team_id} has {nearby}/{min_nodes} nodes "
                        f"within {max_distance:g}"
                    )

        terrain = TerrainMap(cast("Mapping[str, object]", compiled["Terrain"]))
        routes = _as_list(requirements.get("routes", []), "requirements.routes")
        for index, raw_route in enumerate(routes):
            route = _as_object(raw_route, f"requirements.routes[{index}]")
            route_id = _required_string(route.get("id"), f"requirements.routes[{index}].id")
            start = self._resolve_anchor(route.get("from"), f"requirements.routes.{route_id}.from")
            goal = self._resolve_anchor(route.get("to"), f"requirements.routes.{route_id}.to")
            radius = _positive_number(route.get("unit_radius", 8), f"requirements.routes.{route_id}.unit_radius")
            if terrain.can_move_between(start, goal, radius=radius):
                continue
            path = find_path(
                start,
                goal,
                width=terrain.width,
                height=terrain.height,
                can_move_between=lambda current, next_point, route_radius=radius: terrain.can_move_between(
                    current, next_point, radius=route_radius
                ),
            )
            if not path:
                errors.append(f"requirements.routes.{route_id} is unreachable")
        return errors

    def _load_world(self) -> None:
        world = _as_object(self.spec.get("world"), "world")
        self.width = _positive_int(world.get("width"), "world.width")
        self.height = _positive_int(world.get("height"), "world.height")
        symmetry = self.spec.get("symmetry", {})
        symmetry_payload = _as_object(symmetry, "symmetry")
        symmetry_type = symmetry_payload.get("type", "none")
        if symmetry_type not in {"none", "rotate_180"}:
            raise MapSpecError("symmetry.type must be 'none' or 'rotate_180'")
        self.symmetry_type = cast("str", symmetry_type)
        self.symmetry_center = _point(
            symmetry_payload.get("center", [self.width / 2, self.height / 2]),
            "symmetry.center",
        )

    def _load_anchors(self) -> None:
        raw_anchors = _as_object(self.spec.get("anchors", {}), "anchors")
        resolving: set[str] = set()

        def resolve(anchor_id: str) -> Point:
            if anchor_id in self.anchors:
                return self.anchors[anchor_id]
            if anchor_id in resolving:
                raise MapSpecError(f"anchors.{anchor_id} contains a mirror cycle")
            if anchor_id not in raw_anchors:
                raise MapSpecError(f"unknown anchor '{anchor_id}'")
            resolving.add(anchor_id)
            value = raw_anchors[anchor_id]
            if isinstance(value, dict):
                anchor_payload = cast("JsonObject", value)
                mirror_of = _required_string(anchor_payload.get("mirror_of"), f"anchors.{anchor_id}.mirror_of")
                point = self._mirror_point(resolve(mirror_of))
            else:
                point = _point(value, f"anchors.{anchor_id}")
            resolving.remove(anchor_id)
            self.anchors[anchor_id] = point
            return point

        for anchor_id in raw_anchors:
            point = resolve(anchor_id)
            if not 0 <= point[0] <= self.width or not 0 <= point[1] <= self.height:
                raise MapSpecError(f"anchors.{anchor_id} at {list(point)} is outside world {self.width}x{self.height}")

    def _compile_teams(self) -> dict[str, JsonObject]:
        records = _as_list(self.spec.get("teams"), "teams")
        teams: dict[str, JsonObject] = {}
        for index, raw_record in enumerate(records):
            record = _as_object(raw_record, f"teams[{index}]")
            team_id = _required_string(record.get("id"), f"teams[{index}].id")
            if team_id in teams:
                raise MapSpecError(f"duplicate team id '{team_id}'")
            faction_id = _required_string(record.get("faction_id"), f"teams[{index}].faction_id")
            if faction_id not in CONTENT.factions:
                raise MapSpecError(f"teams.{team_id}.faction_id names unknown faction '{faction_id}'")
            anchor = self._resolve_anchor(record.get("start_anchor"), f"teams.{team_id}.start_anchor")
            available = {
                **CONTENT.units_for_faction(faction_id),
                **CONTENT.buildings_for_faction(faction_id),
            }
            team_payload: JsonObject = {"faction_id": faction_id}
            package = _as_object(record.get("starting_package", {}), f"teams.{team_id}.starting_package")
            offset_index = 0
            for content_id, raw_count in package.items():
                if content_id not in available:
                    raise MapSpecError(f"teams.{team_id} cannot place '{content_id}' for faction {faction_id}")
                count = _non_negative_int(raw_count, f"teams.{team_id}.starting_package.{content_id}")
                coords = cast("list[list[int]]", team_payload.setdefault(content_id, []))
                for _ in range(count):
                    offset = _starting_offset(content_id, offset_index)
                    coords.append([anchor[0] + offset[0], anchor[1] + offset[1]])
                    offset_index += 1

            explicit = _as_list(record.get("entities", []), f"teams.{team_id}.entities")
            for entity_index, raw_entity in enumerate(explicit):
                entity = _as_object(raw_entity, f"teams.{team_id}.entities[{entity_index}]")
                content_id = _required_string(
                    entity.get("content"), f"teams.{team_id}.entities[{entity_index}].content"
                )
                if content_id not in available:
                    raise MapSpecError(f"teams.{team_id} cannot place '{content_id}' for faction {faction_id}")
                point = self._position_from_record(entity, anchor, f"teams.{team_id}.entities[{entity_index}]")
                cast("list[list[int]]", team_payload.setdefault(content_id, [])).append(list(point))
            teams[team_id] = team_payload
        return teams

    def _compile_placements(self, teams: dict[str, JsonObject], resources: JsonObject) -> None:
        records = _as_list(self.spec.get("placements", []), "placements")
        for index, raw_record in enumerate(records):
            record = _as_object(raw_record, f"placements[{index}]")
            placement_id = _required_string(record.get("id"), f"placements[{index}].id")
            if placement_id in self.generated_placements:
                raise MapSpecError(f"duplicate placement id '{placement_id}'")
            if "mirror_of" in record:
                source_id = _required_string(record.get("mirror_of"), f"placements.{placement_id}.mirror_of")
                if source_id not in self.generated_placements:
                    raise MapSpecError(f"placements.{placement_id} references unknown earlier placement '{source_id}'")
                generated = [
                    (content_id, team_id, self._mirror_point(point))
                    for content_id, team_id, point in self.generated_placements[source_id]
                ]
            else:
                generated = self._expand_placement(record, placement_id)
            self.generated_placements[placement_id] = generated
            for content_id, team_id, point in generated:
                if content_id in CONTENT.resources:
                    cast("list[list[int]]", resources.setdefault(content_id, [])).append(list(point))
                    continue
                if team_id is None or team_id not in teams:
                    raise MapSpecError(f"placements.{placement_id} requires a known team")
                faction_id = cast("str", teams[team_id]["faction_id"])
                available = {
                    **CONTENT.units_for_faction(faction_id),
                    **CONTENT.buildings_for_faction(faction_id),
                }
                if content_id not in available:
                    raise MapSpecError(
                        f"placements.{placement_id} cannot place '{content_id}' for team {team_id}/{faction_id}"
                    )
                cast("list[list[int]]", teams[team_id].setdefault(content_id, [])).append(list(point))

    def _expand_placement(self, record: JsonObject, placement_id: str) -> list[tuple[str, str | None, Point]]:
        kind = record.get("kind")
        if kind == "resource_cluster":
            content_id = _required_string(record.get("resource"), f"placements.{placement_id}.resource")
            if content_id not in CONTENT.resources:
                raise MapSpecError(f"placements.{placement_id} names unknown resource '{content_id}'")
            team_id = None
        elif kind == "entity_cluster":
            content_id = _required_string(record.get("content"), f"placements.{placement_id}.content")
            if content_id not in CONTENT.units and content_id not in CONTENT.buildings:
                raise MapSpecError(f"placements.{placement_id} names unknown entity '{content_id}'")
            team_id = _required_string(record.get("team"), f"placements.{placement_id}.team")
        elif kind == "entity":
            content_id = _required_string(record.get("content"), f"placements.{placement_id}.content")
            team_id = cast("str | None", record.get("team"))
            base = self._resolve_anchor(record.get("anchor", [0, 0]), f"placements.{placement_id}.anchor")
            point = self._position_from_record(record, base, f"placements.{placement_id}")
            return [(content_id, team_id, point)]
        else:
            raise MapSpecError(
                f"placements.{placement_id}.kind must be 'resource_cluster', 'entity_cluster', or 'entity'"
            )

        anchor = self._resolve_anchor(record.get("anchor"), f"placements.{placement_id}.anchor")
        pattern = _as_object(record.get("pattern"), f"placements.{placement_id}.pattern")
        return [(content_id, team_id, (anchor[0] + dx, anchor[1] + dy)) for dx, dy in _expand_pattern(pattern)]

    def _compile_terrain(self) -> JsonObject:
        terrain: JsonObject = {
            "width": self.width,
            "height": self.height,
            "high_ground": [],
            "ramps": [],
            "water": [],
            "rocks": [],
            "grass": [],
        }
        records = _as_list(self.spec.get("terrain", []), "terrain")
        for index, raw_record in enumerate(records):
            record = _as_object(raw_record, f"terrain[{index}]")
            feature_id = _required_string(record.get("id"), f"terrain[{index}].id")
            if feature_id in self.generated_terrain:
                raise MapSpecError(f"duplicate terrain id '{feature_id}'")
            if "mirror_of" in record:
                source_id = _required_string(record.get("mirror_of"), f"terrain.{feature_id}.mirror_of")
                if source_id not in self.generated_terrain:
                    raise MapSpecError(f"terrain.{feature_id} references unknown earlier feature '{source_id}'")
                kind, geometry = self.generated_terrain[source_id]
                geometry = self._mirror_geometry(kind, geometry)
            else:
                kind = _required_string(record.get("kind"), f"terrain.{feature_id}.kind")
                if kind not in SUPPORTED_TERRAIN:
                    raise MapSpecError(f"terrain.{feature_id}.kind is unsupported: '{kind}'")
                geometry = self._compile_geometry(kind, record.get("geometry"), feature_id)
            self.generated_terrain[feature_id] = (kind, geometry)
            target_key = {"ramp": "ramps", "rock": "rocks", "grass": "grass"}.get(kind, kind)
            cast("list[object]", terrain[target_key]).append(geometry)
        return terrain

    def _compile_geometry(self, kind: str, raw_geometry: object, feature_id: str) -> object:
        geometry = _as_object(raw_geometry, f"terrain.{feature_id}.geometry")
        geometry_type = geometry.get("type")
        if kind in {"rock", "grass"}:
            if geometry_type != "circle":
                raise MapSpecError(f"terrain.{feature_id} requires circle geometry")
            center = _point(geometry.get("center"), f"terrain.{feature_id}.geometry.center")
            radius = _positive_int(geometry.get("radius"), f"terrain.{feature_id}.geometry.radius")
            return [center[0], center[1], radius]
        if geometry_type == "rect":
            rect = _rect(geometry, f"terrain.{feature_id}.geometry")
            return [rect] if kind in {"water", "high_ground"} else rect
        if geometry_type == "rect_group" and kind in {"water", "high_ground"}:
            rects = _as_list(geometry.get("rects"), f"terrain.{feature_id}.geometry.rects")
            if not rects:
                raise MapSpecError(f"terrain.{feature_id}.geometry.rects cannot be empty")
            return [_rect(_as_object(rect, f"terrain.{feature_id}.geometry.rects"), feature_id) for rect in rects]
        raise MapSpecError(f"terrain.{feature_id} requires rect geometry")

    def _mirror_geometry(self, kind: str, geometry: object) -> object:
        if kind in {"rock", "grass"}:
            x, y, radius = cast("list[int]", geometry)
            mirrored = self._mirror_point((x, y))
            return [mirrored[0], mirrored[1], radius]
        if kind in {"water", "high_ground"}:
            return [self._mirror_rect(rect) for rect in cast("list[list[int]]", geometry)]
        return self._mirror_rect(cast("list[int]", geometry))

    def _mirror_rect(self, rect: list[int]) -> list[int]:
        x, y, width, height = rect
        return [
            2 * self.symmetry_center[0] - x - width,
            2 * self.symmetry_center[1] - y - height,
            width,
            height,
        ]

    def _mirror_point(self, point: Point) -> Point:
        if self.symmetry_type != "rotate_180":
            raise MapSpecError("mirror_of requires symmetry.type 'rotate_180'")
        return 2 * self.symmetry_center[0] - point[0], 2 * self.symmetry_center[1] - point[1]

    def _resolve_anchor(self, value: object, label: str) -> Point:
        if isinstance(value, str):
            try:
                return self.anchors[value]
            except KeyError as exc:
                raise MapSpecError(f"{label} references unknown anchor '{value}'") from exc
        return _point(value, label)

    def _position_from_record(self, record: Mapping[str, object], base: Point, label: str) -> Point:
        if "at" in record:
            return _point(record["at"], f"{label}.at")
        offset = _point(record.get("offset", [0, 0]), f"{label}.offset")
        return base[0] + offset[0], base[1] + offset[1]


def _expand_pattern(pattern: JsonObject) -> list[Point]:
    pattern_type = _required_string(pattern.get("type"), "pattern.type")
    if pattern_type not in SUPPORTED_PATTERNS:
        raise MapSpecError(f"pattern.type is unsupported: '{pattern_type}'")
    if pattern_type == "fixed_points":
        return [_point(value, "pattern.points") for value in _as_list(pattern.get("points"), "pattern.points")]
    if pattern_type == "grid":
        rows = _positive_int(pattern.get("rows"), "pattern.rows")
        columns = _positive_int(pattern.get("columns"), "pattern.columns")
        spacing = _point(pattern.get("spacing"), "pattern.spacing")
        return [
            (
                round((column - (columns - 1) / 2) * spacing[0]),
                round((row - (rows - 1) / 2) * spacing[1]),
            )
            for row in range(rows)
            for column in range(columns)
        ]

    count = _positive_int(pattern.get("count"), "pattern.count")
    if pattern_type == "ring":
        radius = _positive_number(pattern.get("radius"), "pattern.radius")
        start = math.radians(_number(pattern.get("start_angle", 0), "pattern.start_angle"))
        return [
            (
                round(math.cos(start + math.tau * index / count) * radius),
                round(math.sin(start + math.tau * index / count) * radius),
            )
            for index in range(count)
        ]
    if pattern_type == "arc":
        radius = _positive_number(pattern.get("radius"), "pattern.radius")
        start = math.radians(_number(pattern.get("start_angle", -90), "pattern.start_angle"))
        end = math.radians(_number(pattern.get("end_angle", 90), "pattern.end_angle"))
        return [
            (
                round(math.cos(start if count == 1 else start + (end - start) * index / (count - 1)) * radius),
                round(math.sin(start if count == 1 else start + (end - start) * index / (count - 1)) * radius),
            )
            for index in range(count)
        ]
    if pattern_type == "line":
        start = _point(pattern.get("from"), "pattern.from")
        end = _point(pattern.get("to"), "pattern.to")
        return [
            (
                round(start[0] if count == 1 else start[0] + (end[0] - start[0]) * index / (count - 1)),
                round(start[1] if count == 1 else start[1] + (end[1] - start[1]) * index / (count - 1)),
            )
            for index in range(count)
        ]
    radius = _positive_number(pattern.get("radius"), "pattern.radius")
    seed = _non_negative_int(pattern.get("seed"), "pattern.seed")
    generator = random.Random(seed)  # noqa: S311 - deterministic layout, not security
    points: list[Point] = []
    for _ in range(count):
        angle = generator.random() * math.tau
        distance = radius * math.sqrt(generator.random())
        points.append((round(math.cos(angle) * distance), round(math.sin(angle) * distance)))
    return points


def _semantic_errors(compiled: JsonObject) -> list[str]:
    from rts_nano.game.terrain import TerrainMap

    terrain = cast("JsonObject", compiled["Terrain"])
    width = cast("int", terrain["width"])
    height = cast("int", terrain["height"])
    errors: list[str] = []
    occupied: dict[tuple[int, int], str] = {}
    terrain_map = TerrainMap(terrain)

    for section_id in ("Blue", "Red"):
        team = cast("JsonObject", compiled[section_id])
        if not team.get("base"):
            errors.append(f"teams.{section_id} must place at least one base")
        for content_id, raw_coords in team.items():
            if content_id == "faction_id":
                continue
            for index, coord in enumerate(cast("list[list[int]]", raw_coords)):
                label = f"teams.{section_id}.{content_id}[{index}]"
                definition = CONTENT.units.get(content_id) or CONTENT.buildings.get(content_id)
                _check_point(coord, label, width, height, errors, radius=definition.radius if definition else 0)
                _check_duplicate(coord, label, occupied, errors)
                if definition is not None and terrain_map.blocks_movement(
                    (coord[0], coord[1]), radius=definition.radius
                ):
                    errors.append(f"{label} overlaps blocking terrain")

    resources = cast("JsonObject", compiled["Resources"])
    for content_id, raw_coords in resources.items():
        for index, coord in enumerate(cast("list[list[int]]", raw_coords)):
            label = f"resources.{content_id}[{index}]"
            definition = CONTENT.resources.get(content_id)
            _check_point(coord, label, width, height, errors, radius=definition.radius if definition else 0)
            _check_duplicate(coord, label, occupied, errors)
            if definition is not None and terrain_map.blocks_movement((coord[0], coord[1]), radius=definition.radius):
                errors.append(f"{label} overlaps blocking terrain")

    for kind in ("high_ground", "water"):
        for group_index, group in enumerate(cast("list[list[list[int]]]", terrain[kind])):
            for rect_index, rect in enumerate(group):
                _check_rect(rect, f"terrain.{kind}[{group_index}][{rect_index}]", width, height, errors)
    for index, rect in enumerate(cast("list[list[int]]", terrain["ramps"])):
        _check_rect(rect, f"terrain.ramps[{index}]", width, height, errors)
    for kind in ("rocks", "grass"):
        for index, circle in enumerate(cast("list[list[int]]", terrain[kind])):
            x, y, radius = circle
            if x - radius < 0 or y - radius < 0 or x + radius > width or y + radius > height:
                errors.append(f"terrain.{kind}[{index}] circle exceeds world bounds")
    return errors


def _check_point(
    point: list[int],
    label: str,
    width: int,
    height: int,
    errors: list[str],
    *,
    radius: int | float,
) -> None:
    if point[0] - radius < 0 or point[0] + radius > width or point[1] - radius < 0 or point[1] + radius > height:
        errors.append(f"{label} at {point} exceeds world {width}x{height} with radius {radius:g}")


def _check_duplicate(point: list[int], label: str, occupied: dict[tuple[int, int], str], errors: list[str]) -> None:
    key = point[0], point[1]
    if key in occupied:
        errors.append(f"{label} duplicates {occupied[key]} at {point}")
    else:
        occupied[key] = label


def _check_rect(rect: list[int], label: str, width: int, height: int, errors: list[str]) -> None:
    x, y, rect_width, rect_height = rect
    if x < 0 or y < 0 or x + rect_width > width or y + rect_height > height:
        errors.append(f"{label} exceeds world bounds")


def _starting_offset(content_id: str, index: int) -> Point:
    if content_id == "base":
        return 0, 0
    ring = index // 8 + 1
    angle = math.tau * (index % 8) / 8
    return round(math.cos(angle) * ring * 55), round(math.sin(angle) * ring * 55)


def _rect(payload: JsonObject, label: str) -> list[int]:
    position = _point(payload.get("position"), f"{label}.position")
    size = _point(payload.get("size"), f"{label}.size")
    if size[0] <= 0 or size[1] <= 0:
        raise MapSpecError(f"{label}.size values must be positive")
    return [position[0], position[1], size[0], size[1]]


def _point(value: object, label: str) -> Point:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise MapSpecError(f"{label} must be [x, y]")
    if not all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in value):
        raise MapSpecError(f"{label} values must be numbers")
    return round(cast("float", value[0])), round(cast("float", value[1]))


def _as_object(value: object, label: str) -> JsonObject:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise MapSpecError(f"{label} must be an object")
    return cast("JsonObject", value)


def _as_list(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise MapSpecError(f"{label} must be a list")
    return cast("list[object]", value)


def _required_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise MapSpecError(f"{label} must be a non-empty string")
    return value


def _number(value: object, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise MapSpecError(f"{label} must be a number")
    return float(value)


def _positive_number(value: object, label: str) -> float:
    result = _number(value, label)
    if result <= 0:
        raise MapSpecError(f"{label} must be positive")
    return result


def _positive_int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise MapSpecError(f"{label} must be a positive integer")
    return value


def _non_negative_int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise MapSpecError(f"{label} must be a non-negative integer")
    return value
