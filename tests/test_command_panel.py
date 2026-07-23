"""Tests for the command-panel layout/logic (decoupled from drawing)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from rts_nano.game.ui.command_panel import CommandPanel
from rts_nano.game.ui.input_controller import InputController
from rts_nano.game.ui.selection_panel import build_selection_panel_layout
from rts_nano.headless import HeadlessSimulation
from rts_nano.simulation.entities.base import TeamColor

if TYPE_CHECKING:
    from rts_nano.map_schema import MapSettings


def _settings() -> MapSettings:
    return {
        "schema_version": 2,
        "Blue": {
            "faction_id": "AEGIS",
            "peasant": [[40, 40]],
            "base": [[120, 120]],
            "guardian": [[60, 200]],
            "marksman": [],
            "arclight": [],
        },
        "Red": {"faction_id": "RUST", "peasant": [], "base": [[350, 350]], "ripper": [], "spitter": [], "brute": []},
        "Resources": {"wood": [], "gold": []},
        "Terrain": {
            "width": 500,
            "height": 400,
            "high_ground": [],
            "water": [],
            "ramps": [],
            "rocks": [],
            "grass": [],
        },
    }


def test_command_panel_peasant_shows_build_buttons() -> None:
    """An AEGIS peasant with resources gets enabled construct buttons for its faction buildings."""
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    peasant = manager.state.entities_by_content_id("peasant", team=TeamColor.BLUE)[0]
    manager.teams[TeamColor.BLUE].resources.update({"wood": 1000, "gold": 1000})
    manager.select_entities_for_team(TeamColor.BLUE, [peasant])

    panel = CommandPanel()
    root_buttons = panel.build(manager, manager.screen_width, manager.screen_height)
    assert next(button for button in root_buttons if button.action == "open_build_menu").hotkey == "B"
    assert panel.show_build_menu(manager)
    buttons = panel.build(manager, manager.screen_width, manager.screen_height)
    construct_types = {button.building_type for button in buttons if button.action == "construct"}

    # House plus the AEGIS tier-1 buildings are immediately buildable; the
    # spire is tech-gated behind an arsenal, so it is not an enabled construct.
    assert {"house", "arsenal", "bastion"} <= construct_types
    assert "spire" in construct_types
    assert not next(button for button in buttons if button.building_type == "spire").enabled
    # RUST buildings never leak into an AEGIS build menu.
    assert {"pit", "chem_vat", "spiker"}.isdisjoint(construct_types)
    assert all(
        button.enabled
        for button in buttons
        if button.action == "construct" and button.building_type in {"house", "arsenal", "bastion"}
    )
    simulation.close()


def test_rust_build_menu_uses_the_registry_tree() -> None:
    """The same build card derives the RUST roster without faction-specific UI tables."""
    settings = _settings()
    settings["Blue"] = {
        "faction_id": "RUST",
        "peasant": [[40, 40]],
        "base": [[120, 120]],
        "knight": [],
        "archer": [],
        "mage": [],
        "ripper": [],
        "spitter": [],
        "brute": [],
    }
    simulation = HeadlessSimulation.from_settings(settings)
    manager = simulation.manager
    peasant = manager.state.entities_by_content_id("peasant", team=TeamColor.BLUE)[0]
    manager.teams[TeamColor.BLUE].resources.update({"wood": 1000, "gold": 1000})
    manager.select_entities_for_team(TeamColor.BLUE, [peasant])
    panel = CommandPanel()

    assert panel.show_build_menu(manager)
    buttons = panel.build(manager, manager.screen_width, manager.screen_height)
    construct_types = {button.building_type for button in buttons if button.action == "construct"}

    assert construct_types == {"house", "pit", "chem_vat", "spiker"}
    assert not next(button for button in buttons if button.building_type == "chem_vat").enabled
    assert {"arsenal", "spire", "bastion"}.isdisjoint(construct_types)
    simulation.close()


def test_command_panel_base_shows_train_button() -> None:
    """A selected base with peasant cost banked exposes an enabled Train Peasant button."""
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    base = manager.state.entities_by_content_id("base", team=TeamColor.BLUE)[0]
    manager.teams[TeamColor.BLUE].resources.update({"wood": 50, "gold": 0})
    manager.select_entities_for_team(TeamColor.BLUE, [base])

    buttons = CommandPanel().build(manager, manager.screen_width, manager.screen_height)
    train = [button for button in buttons if button.action == "produce"]

    assert any(button.unit_type == "peasant" and button.enabled for button in train)
    simulation.close()


def test_command_panel_base_denies_train_without_resources() -> None:
    """Without resources the base's train command surfaces a disabled cost hint."""
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    base = manager.state.entities_by_content_id("base", team=TeamColor.BLUE)[0]
    manager.teams[TeamColor.BLUE].resources.update({"wood": 0, "gold": 0})
    manager.select_entities_for_team(TeamColor.BLUE, [base])

    buttons = CommandPanel().build(manager, manager.screen_width, manager.screen_height)

    train = next(button for button in buttons if button.action == "produce" and button.unit_type == "peasant")
    assert train.enabled is False
    assert train.status == "Not enough resources"
    assert train.cost == "50W"
    simulation.close()


def test_disabled_command_consumes_click_and_hotkey_with_feedback() -> None:
    """Unavailable card actions explain why instead of leaking to global shortcuts."""
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    base = manager.state.entities_by_content_id("base", team=TeamColor.BLUE)[0]
    manager.select_entities_for_team(TeamColor.BLUE, [base])
    controller = InputController()
    train = next(
        button
        for button in controller.presentation.command_panel.build(manager, manager.screen_width, manager.screen_height)
        if button.action == "produce"
    )

    assert controller._handle_command_panel_click(manager, train.rect.center)
    assert manager.menu_status == "Not enough resources"
    manager.menu_status = None
    controller.handle_event(manager, pygame.event.Event(pygame.KEYDOWN, key=pygame.K_q))
    assert manager.menu_status == "Not enough resources"
    simulation.close()


def test_command_panel_unit_shows_unit_commands() -> None:
    """A selected combat unit exposes stop/hold/attack-move/patrol commands."""
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    guardian = manager.state.entities_by_content_id("guardian", team=TeamColor.BLUE)[0]
    manager.select_entities_for_team(TeamColor.BLUE, [guardian])

    buttons = CommandPanel().build(manager, manager.screen_width, manager.screen_height)

    assert {"move", "stop", "hold", "attack_move", "patrol"} <= {button.action for button in buttons}
    assert {button.action: button.slot for button in buttons}["move"] == 0
    assert {button.action: button.hotkey for button in buttons}["move"] == "M"
    simulation.close()


def test_move_button_enters_explicit_targeting_mode() -> None:
    """The new Move command uses the shared command card for click dispatch."""
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    guardian = manager.state.entities_by_content_id("guardian", team=TeamColor.BLUE)[0]
    manager.select_entities_for_team(TeamColor.BLUE, [guardian])
    controller = InputController()
    move = next(
        button
        for button in controller.presentation.command_panel.build(manager, manager.screen_width, manager.screen_height)
        if button.action == "move"
    )

    assert controller._handle_command_panel_click(manager, move.rect.center)
    assert manager.pending_unit_command == "move"
    assert manager.menu_status == "Choose move target"
    simulation.close()


def test_command_panel_click_dispatch_queues_production() -> None:
    """Clicking a built produce button queues the unit, proving render/input share it."""
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    base = manager.state.entities_by_content_id("base", team=TeamColor.BLUE)[0]
    manager.teams[TeamColor.BLUE].resources.update({"wood": 50, "gold": 0})
    manager.select_entities_for_team(TeamColor.BLUE, [base])

    buttons = CommandPanel().build(manager, manager.screen_width, manager.screen_height)
    train = next(button for button in buttons if button.action == "produce" and button.unit_type == "peasant")
    handled = InputController()._handle_command_panel_click(manager, train.rect.center)

    assert handled is True
    assert len(manager.production.queue_for(base)) == 1
    simulation.close()


def test_activity_cancel_does_not_hide_expanded_arsenal_tree() -> None:
    """Four units, four doctrines, and Cancel remain reachable in the 3x3 card."""
    settings = _settings()
    settings["Blue"]["arsenal"] = [[220, 120]]
    simulation = HeadlessSimulation.from_settings(settings)
    manager = simulation.manager
    arsenal = manager.state.entities_by_content_id("arsenal", team=TeamColor.BLUE)[0]
    manager.teams[TeamColor.BLUE].resources.update({"wood": 2000, "gold": 2000})
    assert manager.produce_unit(arsenal, "guardian")
    manager.select_entities_for_team(TeamColor.BLUE, [arsenal])

    buttons = CommandPanel().build(manager, manager.screen_width, manager.screen_height)
    research_ids = {button.upgrade_id for button in buttons if button.action == "research"}

    assert len([button for button in buttons if button.action == "produce"]) == 4
    assert research_ids == {
        "aegis_knight_bulwark",
        "aegis_knight_vanguard",
        "aegis_archer_longshot",
        "aegis_archer_arcshot",
    }
    assert next(button for button in buttons if button.action == "cancel").slot == 8
    simulation.close()


def test_clicking_multi_selection_icon_selects_that_entity() -> None:
    """Selection-card hit testing uses the same rectangles as rendering."""
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    peasant = manager.state.entities_by_content_id("peasant", team=TeamColor.BLUE)[0]
    guardian = manager.state.entities_by_content_id("guardian", team=TeamColor.BLUE)[0]
    manager.select_entities_for_team(TeamColor.BLUE, [peasant, guardian])
    icon_rects = build_selection_panel_layout(2, manager.screen_width, manager.screen_height).icon_rects

    handled = InputController()._handle_selection_panel_click(manager, icon_rects[1].center)

    assert handled is True
    assert manager.selected_entities == [guardian]
    simulation.close()
