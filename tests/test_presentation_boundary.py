"""Regression tests for the pure-entity/presentation boundary."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from rts_nano.application import GameSession
from rts_nano.game.observations import EntityIdRegistry, build_observation
from rts_nano.game.ui.renderer import GameRenderer
from rts_nano.simulation.entities import TeamColor

if TYPE_CHECKING:
    from rts_nano.map_schema import MapSettings


def _settings() -> MapSettings:
    return {
        "schema_version": 2,
        "Blue": {
            "faction_id": "AEGIS",
            "peasant": [[60, 80]],
            "base": [[80, 160]],
            "guardian": [[120, 80]],
            "marksman": [[160, 80]],
            "arclight": [[200, 80]],
            "arsenal": [[160, 160]],
            "spire": [[240, 160]],
            "bastion": [[320, 160]],
        },
        "Red": {
            "faction_id": "RUST",
            "peasant": [[500, 400]],
            "base": [[560, 400]],
            "ripper": [[400, 320]],
            "spitter": [[440, 320]],
            "brute": [[480, 320]],
            "pit": [[400, 400]],
            "chem_vat": [[480, 400]],
            "spiker": [[560, 320]],
        },
        "Resources": {"wood": [[280, 260]], "gold": [[340, 260]]},
        "Terrain": {
            "width": 640,
            "height": 480,
            "high_ground": [],
            "water": [],
            "ramps": [],
            "rocks": [],
            "grass": [],
        },
    }


def _snapshot(manager: GameSession) -> dict[str, object]:
    return build_observation(manager, tick=20, registry=EntityIdRegistry()).to_dict()


def test_rendering_does_not_change_simulation_results() -> None:
    """The same commands produce identical state with or without presentation."""
    rendered = GameSession(_settings())
    headless = GameSession(_settings())
    renderer = GameRenderer()
    screen = pygame.Surface((rendered.screen_width, rendered.screen_height))

    rendered.issue_move_order(TeamColor.BLUE, (300, 240))
    headless.issue_move_order(TeamColor.BLUE, (300, 240))
    for _ in range(20):
        rendered.update()
        renderer.draw(screen, rendered)
        headless.update()

    assert _snapshot(rendered) == _snapshot(headless)


def test_render_smoke_covers_every_current_content_definition() -> None:
    """Every current content type can pass through the Pygame presentation adapter."""
    manager = GameSession(_settings())
    screen = pygame.Surface((manager.screen_width, manager.screen_height))

    GameRenderer().draw(screen, manager)

    assert {str(entity.content_id) for entity in manager.all_entities} == {
        "peasant",
        "guardian",
        "marksman",
        "arclight",
        "ripper",
        "spitter",
        "brute",
        "base",
        "arsenal",
        "spire",
        "bastion",
        "pit",
        "chem_vat",
        "spiker",
        "wood",
        "gold",
    }
