"""Tests for semantic MapSpec v3 compilation and validation."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from rts_nano.ai import ScriptedAI
from rts_nano.headless import HeadlessSimulation
from rts_nano.map_schema import load_map_settings, validate_map_settings
from rts_nano.map_spec import MapSpecError, compile_map_spec
from rts_nano.map_tools import inspect_map_file, render_map_svg
from rts_nano.simulation.entities import TeamColor

COMPETITIVE_MAPS = tuple(Path("src/rts_nano/maps") / f"map_spec_0{index}.json" for index in range(1, 4))
SAMPLE_MAP = COMPETITIVE_MAPS[0]


def _spec() -> dict[str, object]:
    return {
        "schema_version": 3,
        "id": "compiler_test",
        "name": "Compiler Test",
        "world": {"width": 800, "height": 600},
        "symmetry": {"type": "rotate_180", "center": [400, 300]},
        "anchors": {
            "blue_main": [100, 100],
            "red_main": {"mirror_of": "blue_main"},
            "blue_natural": [250, 180],
            "red_natural": {"mirror_of": "blue_natural"},
        },
        "teams": [
            {
                "id": "Blue",
                "faction_id": "AEGIS",
                "start_anchor": "blue_main",
                "starting_package": {"base": 1, "peasant": 2, "guardian": 1},
            },
            {
                "id": "Red",
                "faction_id": "RUST",
                "start_anchor": "red_main",
                "starting_package": {"base": 1, "peasant": 2, "ripper": 1},
            },
        ],
        "placements": [
            {
                "id": "blue_wood",
                "kind": "resource_cluster",
                "resource": "wood",
                "anchor": "blue_natural",
                "pattern": {"type": "ring", "count": 8, "radius": 45},
            },
            {"id": "red_wood", "mirror_of": "blue_wood"},
            {
                "id": "blue_gold",
                "kind": "resource_cluster",
                "resource": "gold",
                "anchor": "blue_natural",
                "pattern": {"type": "arc", "count": 5, "radius": 22, "start_angle": 20, "end_angle": 160},
            },
            {"id": "red_gold", "mirror_of": "blue_gold"},
        ],
        "terrain": [
            {
                "id": "blue_plateau",
                "kind": "high_ground",
                "geometry": {"type": "rect", "position": [20, 260], "size": [120, 80]},
            },
            {"id": "red_plateau", "mirror_of": "blue_plateau"},
            {
                "id": "center_water",
                "kind": "water",
                "geometry": {"type": "rect", "position": [360, 250], "size": [80, 100]},
            },
            {
                "id": "blue_rock",
                "kind": "rock",
                "geometry": {"type": "circle", "center": [220, 400], "radius": 14},
            },
            {"id": "red_rock", "mirror_of": "blue_rock"},
        ],
    }


def test_map_spec_compiles_patterns_and_mirrors_deterministically() -> None:
    """Named patterns expand to stable runtime coordinates and terrain groups."""
    first = compile_map_spec(_spec())
    second = compile_map_spec(_spec())

    assert first == second
    assert first["Terrain"]["width"] == 800
    assert first["Blue"]["base"] == [[100, 100]]
    assert first["Red"]["base"] == [[700, 500]]
    assert len(first["Resources"]["wood"]) == 16
    assert len(first["Resources"]["gold"]) == 10
    assert first["Terrain"]["high_ground"] == [
        [[20, 260, 120, 80]],
        [[660, 260, 120, 80]],
    ]
    assert first["Terrain"]["rocks"] == [[220, 400, 14], [580, 200, 14]]


def test_map_loader_accepts_v3_and_returns_runtime_v2(tmp_path: Path) -> None:
    """The public loader compiles v3 without changing GameSession callers."""
    path = tmp_path / "semantic_map.json"
    path.write_text(json.dumps(_spec()), encoding="utf-8")

    loaded = load_map_settings(path)

    assert loaded["schema_version"] == 2
    assert loaded == compile_map_spec(_spec())

    second = load_map_settings(path)
    loaded["Resources"]["wood"].clear()
    assert second["Resources"]["wood"]


def test_map_spec_rejects_unknown_anchor_with_semantic_path() -> None:
    spec = _spec()
    placements = spec["placements"]
    assert isinstance(placements, list)
    assert isinstance(placements[0], dict)
    placements[0]["anchor"] = "missing_natural"

    errors = validate_map_settings(spec)

    assert errors == ["placements.blue_wood.anchor references unknown anchor 'missing_natural'"]


def test_map_spec_rejects_invalid_anchor_and_mirror_contracts() -> None:
    outside = _spec()
    anchors = outside["anchors"]
    assert isinstance(anchors, dict)
    anchors["outside"] = [900, 100]
    assert validate_map_settings(outside) == ["anchors.outside at [900, 100] is outside world 800x600"]

    without_symmetry = _spec()
    without_symmetry["symmetry"] = {"type": "none"}
    assert validate_map_settings(without_symmetry) == ["mirror_of requires symmetry.type 'rotate_180'"]


def test_map_spec_rejects_content_outside_faction() -> None:
    spec = _spec()
    teams = spec["teams"]
    assert isinstance(teams, list)
    assert isinstance(teams[0], dict)
    teams[0]["starting_package"] = {"base": 1, "ripper": 1}

    with pytest.raises(MapSpecError, match="cannot place 'ripper' for faction AEGIS"):
        compile_map_spec(spec)


def test_map_spec_rejects_duplicate_and_out_of_bounds_generated_points() -> None:
    spec = _spec()
    placements = spec["placements"]
    assert isinstance(placements, list)
    placements.extend(
        [
            {
                "id": "duplicate",
                "kind": "resource_cluster",
                "resource": "wood",
                "anchor": "blue_natural",
                "pattern": {"type": "fixed_points", "points": [[45, 0]]},
            },
            {
                "id": "outside",
                "kind": "resource_cluster",
                "resource": "gold",
                "anchor": [790, 590],
                "pattern": {"type": "fixed_points", "points": [[20, 20]]},
            },
        ]
    )

    errors = validate_map_settings(spec)

    assert any("duplicates resources.wood[0]" in error for error in errors)
    assert any("exceeds world 800x600" in error for error in errors)


def test_map_spec_rejects_resource_on_blocking_terrain() -> None:
    spec = _spec()
    placements = spec["placements"]
    assert isinstance(placements, list)
    placements.append(
        {
            "id": "flooded_gold",
            "kind": "resource_cluster",
            "resource": "gold",
            "anchor": [400, 300],
            "pattern": {"type": "fixed_points", "points": [[0, 0]]},
        }
    )

    errors = validate_map_settings(spec)

    assert any("resources.gold" in error and "overlaps blocking terrain" in error for error in errors)


def test_seeded_scatter_is_repeatable() -> None:
    spec = _spec()
    placements = spec["placements"]
    assert isinstance(placements, list)
    placements.append(
        {
            "id": "seeded_grass_resources",
            "kind": "resource_cluster",
            "resource": "wood",
            "anchor": [400, 500],
            "pattern": {"type": "scatter", "count": 6, "radius": 40, "seed": 17},
        }
    )

    assert compile_map_spec(spec) == compile_map_spec(spec)


def test_grid_pattern_derives_count_from_rows_and_columns() -> None:
    spec = _spec()
    placements = spec["placements"]
    assert isinstance(placements, list)
    placements.append(
        {
            "id": "grid_without_redundant_count",
            "kind": "resource_cluster",
            "resource": "wood",
            "anchor": [400, 450],
            "pattern": {"type": "grid", "rows": 2, "columns": 3, "spacing": [40, 40]},
        }
    )

    compiled = compile_map_spec(spec)

    assert compiled["Resources"]["wood"][-6:] == [
        [360, 430],
        [400, 430],
        [440, 430],
        [360, 470],
        [400, 470],
        [440, 470],
    ]


@pytest.mark.parametrize(
    ("path", "expected_size"),
    zip(COMPETITIVE_MAPS, ((2000, 1400), (2200, 1400), (1600, 1100)), strict=True),
)
def test_repository_v3_maps_load_into_the_headless_runtime(path: Path, expected_size: tuple[int, int]) -> None:
    """Every competitive semantic map is a real playable runtime map."""
    settings = load_map_settings(path)

    assert settings["schema_version"] == 2
    assert (settings["Terrain"]["width"], settings["Terrain"]["height"]) == expected_size
    assert len(settings["Resources"]["wood"]) == 52
    assert len(settings["Resources"]["gold"]) == 30

    simulation = HeadlessSimulation.from_map_file(path)
    simulation.step(2)
    assert simulation.manager.state.tick_count == 2
    assert (simulation.manager.map_width, simulation.manager.map_height) == expected_size


@pytest.mark.parametrize("path", COMPETITIVE_MAPS)
def test_competitive_map_main_route_and_starting_economy_are_playable(path: Path) -> None:
    """A worker can reach center and complete a harvest cycle on every map."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    center = tuple(payload["anchors"]["center"])
    simulation = HeadlessSimulation.from_map_file(path)
    manager = simulation.manager
    peasant = manager.state.entities_by_content_id("peasant", team=TeamColor.BLUE)[0]
    wood = min(
        manager.state.resources_by_content("wood"),
        key=lambda resource: math.dist(peasant.get_center(), resource.get_center()),
    )
    starting_wood = manager.teams[TeamColor.BLUE].resources["wood"]
    manager.issue_gather_order(TeamColor.BLUE, wood, [peasant])
    simulation.step(700)
    assert manager.teams[TeamColor.BLUE].resources["wood"] > starting_wood

    manager.issue_move_order(TeamColor.BLUE, center, [peasant])
    simulation.step(1000)
    assert peasant.get_center() == center


@pytest.mark.parametrize("path", COMPETITIVE_MAPS)
def test_competitive_maps_have_exact_rotational_start_symmetry(path: Path) -> None:
    settings = load_map_settings(path)
    width = settings["Terrain"]["width"]
    height = settings["Terrain"]["height"]

    for content_id in ("base", "peasant"):
        blue = {tuple(point) for point in settings["Blue"].get(content_id, [])}
        red = {tuple(point) for point in settings["Red"].get(content_id, [])}
        assert {(width - x, height - y) for x, y in blue} == red
    for resource_id in ("wood", "gold"):
        points = {tuple(point) for point in settings["Resources"].get(resource_id, [])}
        assert {(width - x, height - y) for x, y in points} == points


@pytest.mark.parametrize("path", COMPETITIVE_MAPS)
def test_scripted_opponent_can_complete_a_match_on_each_map(path: Path) -> None:
    """Existing game AI can gather, build, cross the map, and destroy the rival base."""
    simulation = HeadlessSimulation.from_map_file(path)
    manager = simulation.manager
    opponent = ScriptedAI(manager, TeamColor.RED)

    for _ in range(8000):
        opponent.step()
        manager.update()

    assert manager.game_over_message == "Team Red wins"


def test_requirements_reject_insufficient_starting_resources() -> None:
    spec = _spec()
    spec["requirements"] = {
        "start_resources": {"wood": {"min_nodes": 8, "max_distance": 10}},
    }

    errors = validate_map_settings(spec)

    assert any("Blue has 0/8 nodes within 10" in error for error in errors)
    assert any("Red has 0/8 nodes within 10" in error for error in errors)


def test_requirements_reject_unreachable_named_route() -> None:
    spec = _spec()
    terrain = spec["terrain"]
    assert isinstance(terrain, list)
    terrain.append(
        {
            "id": "world_divider",
            "kind": "water",
            "geometry": {"type": "rect", "position": [350, 0], "size": [100, 600]},
        }
    )
    spec["requirements"] = {
        "routes": [{"id": "start_to_start", "from": "blue_main", "to": "red_main"}],
    }

    assert "requirements.routes.start_to_start is unreachable" in validate_map_settings(spec)


def test_map_inspection_exposes_strategy_and_ascii_layout() -> None:
    report = inspect_map_file(SAMPLE_MAP)

    assert "Map: Crown Divide" in report
    assert "Symmetry: rotate_180" in report
    assert "Nearest wood:" in report
    assert "Route to center:" in report
    assert "ASCII overview:" in report
    assert "Legend: B/R bases" in report


def test_svg_preview_contains_terrain_resources_and_teams() -> None:
    settings = load_map_settings(SAMPLE_MAP)

    svg = render_map_svg(settings, title="Crown Divide")

    assert '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 2000 1400"' in svg
    assert "Crown Divide" in svg
    assert "#3977a8" in svg  # water
    assert "#e3bd2d" in svg  # gold
    assert "#3c74db" in svg  # Blue
    assert "#c74646" in svg  # Red
