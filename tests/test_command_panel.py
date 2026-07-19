"""Tests for the command-panel layout/logic (decoupled from drawing)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rts_nano.game.constants import SCREEN_HEIGHT, SCREEN_WIDTH
from rts_nano.game.ui.input_controller import InputController
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

    buttons = manager.command_panel.build(manager, SCREEN_WIDTH, SCREEN_HEIGHT)
    construct_types = {button.building_type for button in buttons if button.action == "construct"}

    # House plus the AEGIS tier-1 buildings are immediately buildable; the
    # spire is tech-gated behind an arsenal, so it is not an enabled construct.
    assert {"house", "arsenal", "bastion"} <= construct_types
    assert "spire" not in construct_types
    # RUST buildings never leak into an AEGIS build menu.
    assert {"pit", "chem_vat", "spiker"}.isdisjoint(construct_types)
    assert all(button.enabled for button in buttons if button.action == "construct")
    simulation.close()


def test_command_panel_base_shows_train_button() -> None:
    """A selected base with peasant cost banked exposes an enabled Train Peasant button."""
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    base = manager.state.entities_by_content_id("base", team=TeamColor.BLUE)[0]
    manager.teams[TeamColor.BLUE].resources.update({"wood": 50, "gold": 0})
    manager.select_entities_for_team(TeamColor.BLUE, [base])

    buttons = manager.command_panel.build(manager, SCREEN_WIDTH, SCREEN_HEIGHT)
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

    buttons = manager.command_panel.build(manager, SCREEN_WIDTH, SCREEN_HEIGHT)

    assert not any(button.action == "produce" for button in buttons)
    assert any(button.label.startswith("Need") and not button.enabled for button in buttons)
    simulation.close()


def test_command_panel_unit_shows_unit_commands() -> None:
    """A selected combat unit exposes stop/hold/attack-move/patrol commands."""
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    guardian = manager.state.entities_by_content_id("guardian", team=TeamColor.BLUE)[0]
    manager.select_entities_for_team(TeamColor.BLUE, [guardian])

    buttons = manager.command_panel.build(manager, SCREEN_WIDTH, SCREEN_HEIGHT)

    assert {"stop", "hold", "attack_move", "patrol"} <= {button.action for button in buttons}
    simulation.close()


def test_command_panel_click_dispatch_queues_production() -> None:
    """Clicking a built produce button queues the unit, proving render/input share it."""
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    base = manager.state.entities_by_content_id("base", team=TeamColor.BLUE)[0]
    manager.teams[TeamColor.BLUE].resources.update({"wood": 50, "gold": 0})
    manager.select_entities_for_team(TeamColor.BLUE, [base])

    buttons = manager.command_panel.build(manager, SCREEN_WIDTH, SCREEN_HEIGHT)
    train = next(button for button in buttons if button.action == "produce" and button.unit_type == "peasant")
    handled = InputController()._handle_command_panel_click(manager, train.rect.center)

    assert handled is True
    assert len(manager.production.queue_for(base)) == 1
    simulation.close()
