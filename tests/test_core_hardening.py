"""Sprint S5 correctness contracts for spatial, spawn, and dynamic paths."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rts_nano.game.entity_factory import EntityFactory
from rts_nano.headless import HeadlessSimulation
from rts_nano.simulation.entities import TeamColor

if TYPE_CHECKING:
    from rts_nano.map_schema import MapSettings


def _settings() -> MapSettings:
    return {
        "schema_version": 2,
        "Blue": {
            "faction_id": "AEGIS",
            "peasant": [],
            "base": [[50, 50]],
            "guardian": [],
            "marksman": [],
            "arclight": [],
        },
        "Red": {
            "faction_id": "RUST",
            "peasant": [],
            "base": [[370, 270]],
            "ripper": [],
            "spitter": [],
            "brute": [],
        },
        "Resources": {"wood": [], "gold": []},
        "Terrain": {
            "width": 400,
            "height": 300,
            "high_ground": [],
            "water": [],
            "ramps": [],
            "rocks": [],
            "grass": [],
        },
    }


def test_completed_production_waits_until_a_safe_spawn_point_exists() -> None:
    """A paid completed job is retained when the whole map is blocked."""
    settings = _settings()
    settings["Terrain"]["water"] = [[[0, 0, 400, 300]]]
    simulation = HeadlessSimulation.from_settings(settings)
    manager = simulation.manager
    base = manager.state.entities_by_content_id("base", team=TeamColor.BLUE)[0]
    manager.teams[TeamColor.BLUE].resources["wood"] = 50

    assert manager.build_peasant(base)
    manager.production.queue_for(base)[0].remaining_frames = 0
    simulation.step(1)

    assert not manager.state.entities_by_content_id("peasant", team=TeamColor.BLUE)
    assert manager.production.queue_for(base)[0].progress == 1.0

    manager.state.terrain.water.clear()
    manager.state.terrain.water_shapes.clear()
    simulation.step(1)
    peasants = manager.state.entities_by_content_id("peasant", team=TeamColor.BLUE)

    assert len(peasants) == 1
    assert not manager.production.queue_for(base)
    assert peasants[0] in manager.state.spatial_index.query(peasants[0].get_center(), 1)
    simulation.close()


def test_safe_spawn_is_nearest_deterministic_and_clear_of_producer() -> None:
    """Identical worlds choose the same nearest valid producer exit."""
    positions: list[tuple[float, float]] = []
    for _ in range(2):
        simulation = HeadlessSimulation.from_settings(_settings())
        manager = simulation.manager
        base = manager.state.entities_by_content_id("base", team=TeamColor.BLUE)[0]
        manager.teams[TeamColor.BLUE].resources["wood"] = 50
        assert manager.build_peasant(base)
        manager.production.queue_for(base)[0].remaining_frames = 0
        simulation.step(1)
        peasant = manager.state.entities_by_content_id("peasant", team=TeamColor.BLUE)[0]
        positions.append(peasant.get_center())
        assert abs(peasant.x - base.x) >= peasant.radius + base.radius or abs(peasant.y - base.y) >= (
            peasant.radius + base.radius
        )
        simulation.close()

    assert positions[0] == positions[1]


def test_spatial_index_tracks_high_speed_cross_cell_movement() -> None:
    """The published index contains a unit in its post-movement cell."""
    settings = _settings()
    settings["Blue"]["guardian"] = [[20, 150]]
    simulation = HeadlessSimulation.from_settings(settings)
    unit = simulation.units_for_team(TeamColor.BLUE)[0]
    unit.speed = 260

    simulation.manager.issue_move_order(TeamColor.BLUE, (350, 150), [unit])
    simulation.step(1)

    assert unit.x > 250
    assert unit in simulation.manager.state.spatial_index.query(unit.get_center(), 1)
    assert unit not in simulation.manager.state.spatial_index.query((20, 150), 1)
    simulation.close()


def test_splash_query_crosses_spatial_cell_boundary() -> None:
    """Splash candidates on the other side of a grid boundary take damage."""
    settings = _settings()
    settings["Blue"]["arclight"] = [[40, 128]]
    settings["Red"]["ripper"] = [[126, 128], [130, 128]]
    simulation = HeadlessSimulation.from_settings(settings)
    arclight = simulation.manager.state.entities_by_content_id("arclight", team=TeamColor.BLUE)[0]
    targets = simulation.manager.state.entities_by_content_id("ripper", team=TeamColor.RED)
    secondary_life = targets[1].life

    simulation.manager._assign_unit_target(arclight, targets[0].get_center(), targets[0])
    simulation.step(1)

    assert targets[1].life < secondary_life
    simulation.close()


def test_dynamic_building_addition_and_removal_recalculates_active_path() -> None:
    """Active routes follow the obstacle revision instead of deadlocking."""
    settings = _settings()
    settings["Blue"]["guardian"] = [[40, 150]]
    simulation = HeadlessSimulation.from_settings(settings)
    manager = simulation.manager
    unit = simulation.units_for_team(TeamColor.BLUE)[0]
    manager.movement.assign_unit_target(unit, (350, 150))
    assert unit.path == [(350, 150)]

    obstacle = EntityFactory.create("arsenal", 200, 150, TeamColor.BLUE)
    manager.state.add_runtime_entity(obstacle)
    simulation.step(1)

    assert unit.path_obstacle_revision == manager.state.obstacle_revision
    assert any(abs(y - 150) > 30 for _, y in unit.path)

    manager.state.remove_runtime_entity(obstacle)
    simulation.step(1)
    assert unit.path_obstacle_revision == manager.state.obstacle_revision
    simulation.close()


def test_unreachable_order_stops_without_repath_loop() -> None:
    """An unreachable ground order fails once and leaves a stable idle unit."""
    settings = _settings()
    settings["Blue"]["guardian"] = [[40, 150]]
    settings["Terrain"]["water"] = [[[180, 0, 40, 600]]]
    simulation = HeadlessSimulation.from_settings(settings)
    unit = simulation.units_for_team(TeamColor.BLUE)[0]

    simulation.manager.issue_move_order(TeamColor.BLUE, (350, 150), [unit])
    initial_position = unit.get_center()
    simulation.step(200)

    assert unit.path_unreachable is True
    assert unit.state == "IDLE"
    assert unit.get_center() == initial_position
    assert unit.stuck_frames == 0
    simulation.close()


def test_spatial_index_refreshes_after_runtime_building_death() -> None:
    """Dead buildings disappear from lookup in the same removal tick."""
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    building = manager.state.entities_by_content_id("base", team=TeamColor.RED)[0]
    building.life = 0

    simulation.step(1)

    assert building not in manager.state.spatial_index.query(building.get_center(), building.radius + 1)
    simulation.close()


def test_cancelled_construction_leaves_spatial_index_immediately() -> None:
    """Cancellation removes an unfinished obstacle before the next tick."""
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    building = EntityFactory.create("house", 150, 150, TeamColor.BLUE)
    building.start_construction(100)
    manager.state.add_runtime_entity(building)
    assert building in manager.state.spatial_index.query(building.get_center(), 1)

    assert manager.construction.cancel_construction(building)

    assert building not in manager.state.spatial_index.query(building.get_center(), building.radius + 1)
    simulation.close()


def test_tower_acquires_target_across_map_boundary_cells() -> None:
    """Negative spatial cell ranges near the top-left edge remain queryable."""
    settings = _settings()
    settings["Blue"]["bastion"] = [[12, 12]]
    settings["Red"]["ripper"] = [[70, 12]]
    simulation = HeadlessSimulation.from_settings(settings)
    target = simulation.manager.state.entities_by_content_id("ripper", team=TeamColor.RED)[0]
    life_before = target.life

    simulation.step(1)

    assert target.life < life_before
    simulation.close()


def test_single_unit_attack_move_destination_is_clamped_to_map() -> None:
    """Boundary clicks cannot leave attack-move state targeting off-map space."""
    settings = _settings()
    settings["Blue"]["guardian"] = [[40, 150]]
    simulation = HeadlessSimulation.from_settings(settings)
    unit = simulation.units_for_team(TeamColor.BLUE)[0]

    simulation.manager.issue_attack_move_order(TeamColor.BLUE, (-100, -100), [unit])

    assert unit.attack_move_destination == (0, 0)
    assert unit.target_x == 0
    assert unit.target_y == 0
    simulation.close()
