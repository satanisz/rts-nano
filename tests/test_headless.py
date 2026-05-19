"""Tests for no-render simulation helpers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rts_nano.game.assets.entities.base_entities import TeamColor
from rts_nano.headless import HeadlessSimulation

if TYPE_CHECKING:
    from rts_nano.map_schema import MapSettings


def _settings() -> MapSettings:
    return {
        "Blue": {"peasant": [[20, 20]], "base": [[60, 60]], "knight": [], "archer": [], "mage": []},
        "Red": {"peasant": [], "base": [[250, 250]], "knight": [], "archer": [], "mage": []},
        "Resources": {"wood": [], "cristal": []},
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


def _settings_with_barracks() -> MapSettings:
    settings = _settings()
    settings["Blue"]["barracks"] = [[90, 60]]
    settings["Red"]["barracks"] = []
    return settings


def test_headless_simulation_steps_and_issues_orders() -> None:
    """Headless mode can move simulation forward without drawing."""
    simulation = HeadlessSimulation.from_settings(_settings())

    affected = simulation.issue_move_order(TeamColor.BLUE, (120, 120))
    simulation.step(3)

    assert affected == 1
    assert simulation.units_for_team(TeamColor.BLUE)[0].state == "MOVING"
    simulation.close()


def test_manager_public_move_order_helper_assigns_units() -> None:
    """Game manager exposes move orders without requiring private helper access."""
    simulation = HeadlessSimulation.from_settings(_settings())

    affected = simulation.manager.issue_move_order(TeamColor.BLUE, (120, 120))
    simulation.step(3)

    assert affected == 1
    assert simulation.manager.units_for_team(TeamColor.BLUE)[0].state == "MOVING"
    simulation.close()


def test_manager_public_build_helper_reports_success() -> None:
    """Game manager queues production and spawns a peasant after build time."""
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    group = manager.entities[TeamColor.BLUE]
    base = group.bases[0]
    group.resources["wood"] = 50

    assert manager.build_peasant(base) is True
    assert len(group.peasents) == 1
    assert group.resources["wood"] == 0
    assert len(manager.production.queue_for(base)) == 1
    assert manager.build_peasant(base) is False

    simulation.step(60)

    assert len(group.peasents) == 2
    assert not manager.production.queue_for(base)
    simulation.close()


def test_manager_cancels_queued_peasant_with_partial_refund() -> None:
    """Queued production can be canceled before the unit spawns."""
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    group = manager.entities[TeamColor.BLUE]
    base = group.bases[0]
    group.resources["wood"] = 50

    assert manager.build_peasant(base) is True
    assert manager.cancel_peasant_production(base) is True
    assert group.resources["wood"] == 37
    assert not manager.production.queue_for(base)

    simulation.step(60)

    assert len(group.peasents) == 1
    simulation.close()


def test_manager_trains_military_units_from_barracks() -> None:
    """Barracks can queue and complete basic military production."""
    simulation = HeadlessSimulation.from_settings(_settings_with_barracks())
    manager = simulation.manager
    group = manager.entities[TeamColor.BLUE]
    barracks = group.barracks[0]
    group.resources["wood"] = 100
    group.resources["cristal"] = 25

    assert manager.produce_unit(barracks, "knight") is True
    assert group.resources == {"wood": 0, "cristal": 0}
    assert manager.production.queue_for(barracks)[0].unit_type == "knight"

    simulation.step(120)

    assert len(group.knights) == 1
    assert not manager.production.queue_for(barracks)
    simulation.close()


def test_worker_constructs_barracks_before_military_production() -> None:
    """A peasant can place, build, and unlock a Barracks over time."""
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    group = manager.entities[TeamColor.BLUE]
    peasant = group.peasents[0]
    peasant.x, peasant.y = 150, 120
    group.resources.update({"wood": 220, "cristal": 60})

    assert manager.construct_building(peasant, "barracks", (150, 70)) is True
    assert group.resources == {"wood": 0, "cristal": 0}

    barracks = group.barracks[0]
    assert barracks.is_under_construction is True
    assert barracks.construction_progress == 0
    assert manager.produce_unit(barracks, "knight") is False

    simulation.step(430)

    assert barracks.is_under_construction is False
    assert barracks.construction_progress == 1

    group.resources.update({"wood": 100, "cristal": 25})
    assert manager.produce_unit(barracks, "knight") is True
    simulation.close()


def test_completed_house_increases_population_cap() -> None:
    """Only completed support buildings increase population capacity."""
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    group = manager.entities[TeamColor.BLUE]
    peasant = group.peasents[0]
    peasant.x, peasant.y = 170, 130
    group.resources.update({"wood": 80, "cristal": 0})

    assert manager.population_cap_for_team(TeamColor.BLUE) == 10
    assert manager.construct_building(peasant, "house", (170, 80)) is True

    house = group.houses[0]
    assert house.is_under_construction is True
    assert manager.population_cap_for_team(TeamColor.BLUE) == 10

    simulation.step(250)

    assert house.is_under_construction is False
    assert manager.population_cap_for_team(TeamColor.BLUE) == 16
    simulation.close()


def test_canceling_unfinished_house_refunds_and_removes_building() -> None:
    """Unfinished construction can be canceled for a partial refund."""
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    group = manager.entities[TeamColor.BLUE]
    peasant = group.peasents[0]
    peasant.x, peasant.y = 170, 130
    group.resources.update({"wood": 80, "cristal": 0})

    assert manager.construct_building(peasant, "house", (170, 80)) is True
    house = group.houses[0]

    assert manager.cancel_construction(house) is True

    assert group.resources["wood"] == 60
    assert group.houses == []
    assert peasant.state == "IDLE"
    assert peasant.target_entity is None
    assert manager.cancel_construction(house) is False
    simulation.close()


def test_manager_placement_helpers_place_selected_worker_building() -> None:
    """Pygame UI placement helpers use the same construction validation."""
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    group = manager.entities[TeamColor.BLUE]
    peasant = group.peasents[0]
    peasant.x, peasant.y = 170, 130
    group.resources.update({"wood": 80, "cristal": 0})
    manager.select_entities_for_team(TeamColor.BLUE, [peasant])

    assert manager.begin_construction_placement("house") is True
    assert manager.pending_construction_type == "house"
    assert manager.place_pending_construction((170, 80)) is True

    assert manager.pending_construction_type is None
    assert len(group.houses) == 1
    assert group.houses[0].is_under_construction is True
    simulation.close()


def test_group_move_order_assigns_formation_slots() -> None:
    """Group movement spreads units around the clicked destination."""
    settings = _settings()
    settings["Blue"]["peasant"] = [[20, 20], [28, 20], [36, 20], [44, 20]]
    simulation = HeadlessSimulation.from_settings(settings)

    affected = simulation.issue_move_order(TeamColor.BLUE, (160, 160))
    targets = {(round(unit.target_x), round(unit.target_y)) for unit in simulation.units_for_team(TeamColor.BLUE)}

    assert affected == 4
    assert len(targets) == 4
    simulation.close()


def test_stuck_unit_skips_blocked_waypoint() -> None:
    """A moving unit can recover when collision resolution prevents progress."""
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    unit = simulation.units_for_team(TeamColor.BLUE)[0]
    unit.state = "MOVING"
    unit.path = [(80, 20), (120, 20)]

    for _ in range(75):
        manager._update_unit_stuck_recovery(unit)

    assert unit.path == [(120, 20)]
    simulation.close()


def test_peasant_starts_harvesting_targeted_resources() -> None:
    """A peasant can finish the final path waypoint beside a resource."""
    settings = _settings()
    settings["Resources"]["wood"] = [[100, 20]]
    settings["Resources"]["cristal"] = [[20, 100]]
    simulation = HeadlessSimulation.from_settings(settings)
    manager = simulation.manager
    peasant = manager.entities[TeamColor.BLUE].peasents[0]

    wood = manager.resources.woods[0]
    manager._assign_unit_target(peasant, wood.get_center(), wood)
    simulation.step(80)

    assert peasant.carry_wood > 0

    peasant.x, peasant.y = 20, 20
    peasant.carry_wood = 0
    peasant.state = "IDLE"
    cristal = manager.resources.cristals[0]
    manager._assign_unit_target(peasant, cristal.get_center(), cristal)
    simulation.step(80)

    assert peasant.carry_cristal > 0
    simulation.close()


def test_peasant_harvests_resource_beyond_ramp_edge() -> None:
    """A* should not choose a diagonal shortcut that local movement rejects."""
    simulation = HeadlessSimulation.from_map_file(Path("src/rts_nano/maps/map_settings_01.json"))
    manager = simulation.manager
    peasant = manager.entities[TeamColor.BLUE].peasents[0]
    crystal = manager.resources.cristals[0]

    manager._assign_unit_target(peasant, crystal.get_center(), crystal)
    simulation.step(400)

    assert peasant.carry_cristal > 0
    simulation.close()


def test_unit_path_is_not_blocked_by_neutral_resources() -> None:
    """Neutral resources are selectable targets, not pathfinding blockers."""
    simulation = HeadlessSimulation.from_map_file(Path("src/rts_nano/maps/map_settings_01.json"))
    manager = simulation.manager
    knight = manager.entities[TeamColor.BLUE].knights[0]

    manager._assign_unit_target(knight, (1000, 500))
    simulation.step(300)

    assert knight.state == "IDLE"
    assert not knight.path
    assert knight.get_center() == (1000, 500)
    simulation.close()
