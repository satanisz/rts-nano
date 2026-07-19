"""Tests for no-render simulation helpers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pygame

from rts_nano.game.assets.entities.base_entities import TeamColor
from rts_nano.game.ui.input_controller import InputController
from rts_nano.headless import HeadlessSimulation

if TYPE_CHECKING:
    from rts_nano.map_schema import MapSettings


def _settings() -> MapSettings:
    return {
        "Blue": {"peasant": [[20, 20]], "base": [[60, 60]], "guardian": [], "marksman": [], "arclight": []},
        "Red": {"peasant": [], "base": [[250, 250]], "ripper": [], "spitter": [], "brute": []},
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


def _settings_with_arsenal() -> MapSettings:
    settings = _settings()
    settings["Blue"]["arsenal"] = [[90, 60]]
    settings["Red"]["pit"] = []
    return settings


def test_headless_simulation_steps_and_issues_orders() -> None:
    """Headless mode can move simulation forward without drawing."""
    simulation = HeadlessSimulation.from_settings(_settings())

    affected = simulation.issue_move_order(TeamColor.BLUE, (120, 120))
    simulation.step(3)

    assert affected == 1
    assert simulation.units_for_team(TeamColor.BLUE)[0].state == "MOVING"
    simulation.close()


def test_headless_entities_skip_visual_asset_loading() -> None:
    """No-render simulations do not allocate sprites or portraits per entity."""
    settings = _settings()
    settings["Resources"]["wood"] = [[100, 100]]
    simulation = HeadlessSimulation.from_settings(settings)

    assert simulation.manager.state.load_visuals is False
    assert all(entity.image is None for entity in simulation.manager.all_entities)
    assert all(entity.avatar_image is None for entity in simulation.manager.all_entities)
    simulation.close()


def test_unit_path_routes_around_non_target_building() -> None:
    """Dynamic buildings block A* edges while remaining approachable as targets."""
    settings = _settings()
    settings["Blue"].update({"peasant": [], "base": [[200, 150]], "guardian": [[50, 150]]})
    settings["Red"]["base"] = [[390, 290]]
    simulation = HeadlessSimulation.from_settings(settings)
    manager = simulation.manager
    guardian = manager.entities[TeamColor.BLUE].knights[0]

    assert manager.issue_move_order(TeamColor.BLUE, (350, 150), [guardian]) == 1
    assert guardian.path
    assert any(abs(waypoint_y - 150) > 30 for _, waypoint_y in guardian.path)

    simulation.step(180)

    assert guardian.x > 300
    simulation.close()


def test_manager_public_move_order_helper_assigns_units() -> None:
    """Game manager exposes move orders without requiring private helper access."""
    simulation = HeadlessSimulation.from_settings(_settings())

    affected = simulation.manager.issue_move_order(TeamColor.BLUE, (120, 120))
    simulation.step(3)

    assert affected == 1
    assert simulation.manager.units_for_team(TeamColor.BLUE)[0].state == "MOVING"
    simulation.close()


def test_collision_keeps_crowded_units_on_map_and_off_terrain() -> None:
    """Collision separation never pushes a unit off-map or into blocked terrain."""
    settings: MapSettings = {
        "Blue": {
            "peasant": [],
            "base": [[400, 400]],
            "guardian": [[30 + (i % 4) * 3, 30 + (i // 4) * 3] for i in range(16)],
            "marksman": [],
            "arclight": [],
        },
        "Red": {"peasant": [], "base": [[700, 700]], "ripper": [], "spitter": [], "brute": []},
        "Resources": {"wood": [], "gold": []},
        "Terrain": {
            "width": 800,
            "height": 800,
            "high_ground": [],
            "water": [[[0, 80, 200, 40]]],
            "ramps": [],
            "rocks": [[120, 40, 30]],
            "grass": [],
        },
    }
    simulation = HeadlessSimulation.from_settings(settings)
    manager = simulation.manager
    knights = manager.entities[TeamColor.BLUE].knights

    manager.issue_move_order(TeamColor.BLUE, (40, 40), knights)
    for _ in range(120):
        simulation.step(1)

    for knight in knights:
        assert 0 <= knight.x <= 800
        assert 0 <= knight.y <= 800
        assert not manager.terrain.blocks_movement((knight.x, knight.y), radius=0)
    simulation.close()


def test_manager_public_attack_move_acquires_hostile_target() -> None:
    """Attack-move keeps a route but retargets visible hostiles."""
    settings = _settings()
    settings["Blue"]["peasant"] = []
    settings["Blue"]["guardian"] = [[20, 20]]
    settings["Red"]["peasant"] = [[120, 20]]
    simulation = HeadlessSimulation.from_settings(settings)
    manager = simulation.manager
    knight = manager.entities[TeamColor.BLUE].knights[0]
    enemy = manager.entities[TeamColor.RED].peasents[0]

    affected = manager.issue_attack_move_order(TeamColor.BLUE, (250, 20), [knight])
    simulation.step(3)

    assert affected == 1
    assert knight.attack_move_destination is not None
    assert knight.target_entity is enemy
    simulation.close()


def _wide_patrol_settings() -> MapSettings:
    """Wide map with the rival base far from the patrol route.

    Keeping the only enemy entity out of acquisition range lets the oscillation
    test observe pure patrol movement without the unit diverting to a target.
    """
    return {
        "Blue": {"peasant": [], "base": [[60, 60]], "guardian": [[40, 150]], "marksman": [], "arclight": []},
        "Red": {"peasant": [], "base": [[760, 280]], "ripper": [], "spitter": [], "brute": []},
        "Resources": {"wood": [], "gold": []},
        "Terrain": {
            "width": 800,
            "height": 300,
            "high_ground": [],
            "water": [],
            "ramps": [],
            "rocks": [],
            "grass": [],
        },
    }


def test_manager_patrol_order_oscillates_between_waypoints() -> None:
    """A patrolling unit advances toward its waypoint and loops back."""
    simulation = HeadlessSimulation.from_settings(_wide_patrol_settings())
    manager = simulation.manager
    knight = manager.entities[TeamColor.BLUE].knights[0]

    affected = manager.issue_patrol_order(TeamColor.BLUE, (340, 150), [knight])

    assert affected == 1
    assert knight.current_order is not None
    assert knight.current_order.kind == "patrol"
    assert knight.patrol_points is not None

    reached_far = False
    returned_after_far = False
    for _ in range(600):
        simulation.step(1)
        if knight.x > 300:
            reached_far = True
        elif reached_far and knight.x < 100:
            returned_after_far = True

    assert reached_far
    assert returned_after_far
    simulation.close()


def test_stop_order_cancels_active_patrol() -> None:
    """Issuing a manual stop clears the patrol route and retags the order."""
    settings = _settings()
    settings["Blue"]["peasant"] = []
    settings["Blue"]["guardian"] = [[40, 150]]
    simulation = HeadlessSimulation.from_settings(settings)
    manager = simulation.manager
    knight = manager.entities[TeamColor.BLUE].knights[0]

    manager.issue_patrol_order(TeamColor.BLUE, (300, 150), [knight])
    simulation.step(10)
    manager.issue_stop_order(TeamColor.BLUE, [knight])

    assert knight.patrol_points is None
    assert knight.current_order is not None
    assert knight.current_order.kind == "stop"
    simulation.close()


def test_patrol_unit_acquires_hostile_target_along_route() -> None:
    """A patrolling unit retargets hostiles encountered on its route."""
    settings = _settings()
    settings["Blue"]["peasant"] = []
    settings["Blue"]["guardian"] = [[40, 150]]
    settings["Red"]["peasant"] = [[180, 150]]
    simulation = HeadlessSimulation.from_settings(settings)
    manager = simulation.manager
    knight = manager.entities[TeamColor.BLUE].knights[0]
    enemy = manager.entities[TeamColor.RED].peasents[0]

    manager.issue_patrol_order(TeamColor.BLUE, (300, 150), [knight])
    acquired = False
    for _ in range(200):
        simulation.step(1)
        if knight.target_entity is enemy:
            acquired = True
            break

    assert acquired
    simulation.close()


def test_manager_public_gather_order_sends_peasant_to_resource() -> None:
    """Gather helper targets resources without direct private manager access."""
    settings = _settings()
    settings["Resources"]["wood"] = [[100, 20]]
    simulation = HeadlessSimulation.from_settings(settings)
    manager = simulation.manager
    peasant = manager.entities[TeamColor.BLUE].peasents[0]
    wood = manager.resources.woods[0]

    affected = manager.issue_gather_order(TeamColor.BLUE, wood, [peasant])
    simulation.step(80)

    assert affected == 1
    assert peasant.carry_wood > 0
    simulation.close()


def test_manager_build_hotkeys_enter_worker_placement_modes() -> None:
    """Worker build hotkeys start construction placement for supported buildings."""
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    input_controller = InputController()
    group = manager.entities[TeamColor.BLUE]
    peasant = group.peasents[0]
    group.resources.update({"wood": 220, "gold": 60})
    manager.select_entities_for_team(TeamColor.BLUE, [peasant])

    input_controller.handle_event(manager, pygame.event.Event(pygame.KEYDOWN, key=pygame.K_y))

    assert manager.pending_construction_type == "house"

    manager.cancel_pending_construction_placement()
    input_controller.handle_event(manager, pygame.event.Event(pygame.KEYDOWN, key=pygame.K_b))

    assert manager.pending_construction_type == "arsenal"
    simulation.close()


def test_manager_public_stop_order_clears_unit_targets() -> None:
    """Game manager exposes a stop order for selected or explicit units."""
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    unit = simulation.units_for_team(TeamColor.BLUE)[0]

    manager.issue_move_order(TeamColor.BLUE, (120, 120))
    assert unit.state == "MOVING"

    affected = manager.issue_stop_order(TeamColor.BLUE, [unit])

    assert affected == 1
    assert unit.state == "IDLE"
    assert unit.target_entity is None
    assert unit.path == []
    simulation.close()


def test_manager_public_hold_order_keeps_unit_stationary() -> None:
    """Hold position leaves a unit idle-like but explicitly holding."""
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    unit = simulation.units_for_team(TeamColor.BLUE)[0]

    manager.issue_move_order(TeamColor.BLUE, (120, 120))
    affected = manager.issue_hold_order(TeamColor.BLUE, [unit])
    simulation.step(3)

    assert affected == 1
    assert unit.state == "HOLDING"
    assert unit.target_entity is None
    assert unit.path == []
    assert unit.get_center() == (20, 20)
    simulation.close()


def test_manager_public_return_cargo_order_deposits_resources() -> None:
    """Return cargo sends only carrying peasants to an allied base."""
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    peasant = manager.entities[TeamColor.BLUE].peasents[0]
    peasant.carry_gold = 4

    affected = manager.issue_return_cargo_order(TeamColor.BLUE, [peasant])

    assert affected == 1
    assert peasant.state == "MOVING"
    simulation.step(30)
    assert peasant.carry_gold == 0
    assert manager.entities[TeamColor.BLUE].resources["gold"] == 4
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


def test_manager_trains_military_units_from_arsenal() -> None:
    """An arsenal can queue and complete basic AEGIS military production."""
    simulation = HeadlessSimulation.from_settings(_settings_with_arsenal())
    manager = simulation.manager
    group = manager.entities[TeamColor.BLUE]
    arsenal = group.barracks[0]
    group.resources["wood"] = 110
    group.resources["gold"] = 55

    assert manager.produce_unit(arsenal, "guardian") is True
    assert group.resources == {"wood": 0, "gold": 0}
    assert manager.production.queue_for(arsenal)[0].unit_type == "guardian"

    simulation.step(150)

    assert len(group.knights) == 1
    assert not manager.production.queue_for(arsenal)
    simulation.close()


def test_worker_constructs_arsenal_before_military_production() -> None:
    """A peasant can place, build, and unlock an Arsenal over time."""
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    group = manager.entities[TeamColor.BLUE]
    peasant = group.peasents[0]
    peasant.x, peasant.y = 150, 120
    group.resources.update({"wood": 220, "gold": 60})

    assert manager.construct_building(peasant, "arsenal", (150, 70)) is True
    assert group.resources == {"wood": 0, "gold": 0}

    arsenal = group.barracks[0]
    assert arsenal.is_under_construction is True
    assert arsenal.construction_progress == 0
    assert manager.produce_unit(arsenal, "guardian") is False

    simulation.step(430)

    assert arsenal.is_under_construction is False
    assert arsenal.construction_progress == 1

    group.resources.update({"wood": 110, "gold": 55})
    assert manager.produce_unit(arsenal, "guardian") is True
    simulation.close()


def test_spire_requires_arsenal_before_construction() -> None:
    """The AEGIS spire is tech-gated behind a completed arsenal."""
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    group = manager.entities[TeamColor.BLUE]
    group.resources.update({"wood": 1000, "gold": 1000})

    can_build, reason = manager.construction.can_team_construct(TeamColor.BLUE, "spire")

    assert can_build is False
    assert reason == "missing_tech"
    simulation.close()


def test_worker_constructs_spire_and_trains_arclight() -> None:
    """With an arsenal standing, a peasant can raise a Spire that trains arclights."""
    simulation = HeadlessSimulation.from_settings(_settings_with_arsenal())
    manager = simulation.manager
    group = manager.entities[TeamColor.BLUE]
    peasant = group.peasents[0]
    peasant.x, peasant.y = 250, 240
    group.resources.update({"wood": 200, "gold": 150})

    assert manager.construct_building(peasant, "spire", (250, 200)) is True
    assert group.resources == {"wood": 0, "gold": 0}

    spire = group.mage_towers[0]
    assert spire.is_under_construction is True
    assert manager.produce_unit(spire, "arclight") is False

    simulation.step(560)

    assert spire.is_under_construction is False
    assert spire.construction_progress == 1

    group.resources.update({"wood": 80, "gold": 130})
    assert manager.produce_unit(spire, "arclight") is True

    simulation.step(180)

    assert len(group.mages) == 1
    assert not manager.production.queue_for(spire)
    simulation.close()


def _tower_combat_settings() -> MapSettings:
    """Map with a completed Blue bastion and the rival base out of bastion range."""
    settings = _settings()
    settings["Blue"]["peasant"] = []
    settings["Blue"]["bastion"] = [[150, 150]]
    settings["Red"]["ripper"] = [[250, 150]]
    settings["Red"]["base"] = [[380, 280]]
    return settings


def test_tower_auto_attacks_enemy_in_range() -> None:
    """A completed tower damages a hostile unit inside its attack range."""
    simulation = HeadlessSimulation.from_settings(_tower_combat_settings())
    manager = simulation.manager
    tower = manager.entities[TeamColor.BLUE].towers[0]
    enemy = manager.entities[TeamColor.RED].knights[0]

    assert tower.is_under_construction is False
    start_life = enemy.life

    simulation.step(180)

    assert enemy.life < start_life
    simulation.close()


def test_tower_does_not_attack_while_under_construction() -> None:
    """An unfinished tower deals no damage even with an enemy in range."""
    simulation = HeadlessSimulation.from_settings(_tower_combat_settings())
    manager = simulation.manager
    tower = manager.entities[TeamColor.BLUE].towers[0]
    enemy = manager.entities[TeamColor.RED].knights[0]

    tower.start_construction(240)
    assert tower.is_under_construction is True
    start_life = enemy.life

    simulation.step(180)

    assert enemy.life == start_life
    simulation.close()


def test_tower_ignores_enemy_beyond_attack_range() -> None:
    """A tower does not fire at hostiles outside its attack reach."""
    settings = _tower_combat_settings()
    # Widen the map so the enemy sits clearly past the bastion's effective reach
    # (attack_range + both radii) and cannot be clipped at the edge.
    settings["Terrain"]["width"] = 600
    settings["Red"]["ripper"] = [[430, 150]]
    simulation = HeadlessSimulation.from_settings(settings)
    manager = simulation.manager
    enemy = manager.entities[TeamColor.RED].knights[0]

    start_life = enemy.life

    simulation.step(180)

    assert enemy.life == start_life
    simulation.close()


def test_completed_house_increases_population_cap() -> None:
    """Only completed support buildings increase population capacity."""
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    group = manager.entities[TeamColor.BLUE]
    peasant = group.peasents[0]
    peasant.x, peasant.y = 170, 130
    group.resources.update({"wood": 80, "gold": 0})

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
    group.resources.update({"wood": 80, "gold": 0})

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
    group.resources.update({"wood": 80, "gold": 0})
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
        manager.movement.update_unit_stuck_recovery(unit)

    assert unit.path == [(120, 20)]
    simulation.close()


def test_peasant_starts_harvesting_targeted_resources() -> None:
    """A peasant can finish the final path waypoint beside a resource."""
    settings = _settings()
    settings["Resources"]["wood"] = [[100, 20]]
    settings["Resources"]["gold"] = [[20, 100]]
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
    gold = manager.resources.golds[0]
    manager._assign_unit_target(peasant, gold.get_center(), gold)
    simulation.step(80)

    assert peasant.carry_gold > 0
    simulation.close()


def _selection_settings() -> MapSettings:
    settings = _settings()
    settings["Blue"]["peasant"] = [[20, 20], [40, 20]]
    settings["Blue"]["guardian"] = [[80, 20], [100, 20]]
    return settings


def test_control_group_assign_and_recall_restores_selection() -> None:
    """A stored control group reselects its members after selecting other units."""
    simulation = HeadlessSimulation.from_settings(_selection_settings())
    manager = simulation.manager
    group = manager.entities[TeamColor.BLUE]

    manager.select_entities_for_team(TeamColor.BLUE, group.knights)
    assert manager.assign_control_group(1) == 2

    manager.select_entities_for_team(TeamColor.BLUE, group.peasents)
    assert manager.recall_control_group(1) == 2
    assert set(manager.selected_entities) == set(group.knights)
    simulation.close()


def test_control_group_recall_skips_dead_members() -> None:
    """Recalling a control group drops members that have since died."""
    simulation = HeadlessSimulation.from_settings(_selection_settings())
    manager = simulation.manager
    group = manager.entities[TeamColor.BLUE]

    manager.select_entities_for_team(TeamColor.BLUE, group.knights)
    manager.assign_control_group(2)
    group.knights[0].life = 0

    assert manager.recall_control_group(2) == 1
    simulation.close()


def test_select_units_like_selects_same_type() -> None:
    """Selecting like a unit selects every current-team unit of that type."""
    simulation = HeadlessSimulation.from_settings(_selection_settings())
    manager = simulation.manager
    group = manager.entities[TeamColor.BLUE]

    selected = manager.select_units_like(group.knights[0])

    assert selected == 2
    assert set(manager.selected_entities) == set(group.knights)
    simulation.close()


def test_peasant_gather_cycle_banks_resources() -> None:
    """The gather system runs the full harvest-return-deposit cycle into the bank."""
    settings = _settings()
    settings["Blue"]["base"] = [[60, 60]]
    settings["Blue"]["peasant"] = [[90, 60]]
    settings["Resources"]["wood"] = [[110, 60]]
    simulation = HeadlessSimulation.from_settings(settings)
    manager = simulation.manager
    group = manager.entities[TeamColor.BLUE]
    peasant = group.peasents[0]
    wood = manager.resources.woods[0]

    assert group.resources["wood"] == 0
    manager.issue_gather_order(TeamColor.BLUE, wood, [peasant])
    simulation.step(200)

    assert group.resources["wood"] > 0
    simulation.close()


def test_peasant_harvests_resource_beyond_ramp_edge() -> None:
    """A* should not choose a diagonal shortcut that local movement rejects."""
    simulation = HeadlessSimulation.from_map_file(Path("src/rts_nano/maps/map_settings_01.json"))
    manager = simulation.manager
    peasant = manager.entities[TeamColor.BLUE].peasents[0]
    gold = manager.resources.golds[0]

    manager._assign_unit_target(peasant, gold.get_center(), gold)
    simulation.step(400)

    assert peasant.carry_gold > 0
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
