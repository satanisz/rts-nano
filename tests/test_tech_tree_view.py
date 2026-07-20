"""Generated technology graph and English windowed view tests."""

from __future__ import annotations

import pygame

from rts_nano.game.ui.input_controller import InputController
from rts_nano.game.ui.renderer import GameRenderer
from rts_nano.game.ui.state import PresentationState
from rts_nano.game.ui.tech_tree import build_tech_tree, validate_technology_graph
from rts_nano.headless import HeadlessSimulation
from rts_nano.simulation.entities import TeamColor


def _simulation() -> HeadlessSimulation:
    return HeadlessSimulation.from_settings(
        {
            "schema_version": 2,
            "Blue": {"faction_id": "AEGIS", "base": [[100, 100]]},
            "Red": {"faction_id": "RUST", "base": [[700, 500]]},
            "Resources": {"wood": [], "gold": []},
            "Terrain": {
                "width": 800,
                "height": 600,
                "high_ground": [],
                "water": [],
                "ramps": [],
                "rocks": [],
                "grass": [],
            },
        }
    )


def test_shipped_technology_graph_is_reachable_and_has_paired_doctrines() -> None:
    assert validate_technology_graph() == []


def test_view_model_is_registry_derived_and_reflects_team_choices() -> None:
    simulation = _simulation()
    team = simulation.manager.teams[TeamColor.BLUE]
    initial = build_tech_tree(team)
    assert len(initial) == 8
    assert all(row.name and row.producer and row.description for row in initial)
    assert simulation.manager.upgrades.complete(TeamColor.BLUE, "aegis_knight_bulwark")
    rows = {row.upgrade_id: row for row in build_tech_tree(team)}
    assert rows["aegis_knight_bulwark"].status == "COMPLETED"
    assert rows["aegis_knight_vanguard"].status == "LOCKED BY CHOICE"
    simulation.close()


def test_f9_toggles_overlay_and_renderer_draws_without_mutating_simulation() -> None:
    simulation = _simulation()
    manager = simulation.manager
    presentation = PresentationState()
    controller = InputController(presentation)
    renderer = GameRenderer(presentation=presentation)
    before = (
        manager.state.tick_count,
        tuple((entity.entity_id, entity.x, entity.y, entity.life) for entity in manager.all_entities),
    )
    controller.handle_event(manager, pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F9, mod=0))
    assert presentation.tech_tree_visible
    surface = pygame.Surface((manager.screen_width, manager.screen_height))
    renderer.draw(surface, manager)
    after = (
        manager.state.tick_count,
        tuple((entity.entity_id, entity.x, entity.y, entity.life) for entity in manager.all_entities),
    )
    assert after == before
    controller.handle_event(manager, pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F9, mod=0))
    assert not presentation.tech_tree_visible
    simulation.close()
