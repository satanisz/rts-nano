"""Shared layout for selection portraits used by rendering and input."""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from rts_nano.game.constants import BOTTOM_MENU_HEIGHT, MINIMAP_PADDING, MINIMAP_WIDTH

COMMAND_CARD_WIDTH = 180
PORTRAIT_SIZE = 120
PORTRAIT_BOX_WIDTH = PORTRAIT_SIZE + 20
SELECTION_ICON_SIZE = 40
SELECTION_ICON_PADDING = 8


@dataclass(frozen=True, slots=True)
class SelectionPanelLayout:
    """Screen-space regions for selection details and multi-selection icons."""

    center_panel_x: int
    center_panel_width: int
    portrait_x: int
    icon_rects: tuple[pygame.Rect, ...]


def build_selection_panel_layout(
    selection_count: int,
    screen_width: int,
    screen_height: int,
) -> SelectionPanelLayout:
    """Return one deterministic layout shared by drawing and hit testing."""
    center_panel_x = MINIMAP_WIDTH + MINIMAP_PADDING * 2
    portrait_x = screen_width - COMMAND_CARD_WIDTH - PORTRAIT_BOX_WIDTH
    center_panel_width = max(0, portrait_x - center_panel_x)
    if selection_count <= 1:
        return SelectionPanelLayout(center_panel_x, center_panel_width, portrait_x, ())

    stride = SELECTION_ICON_SIZE + SELECTION_ICON_PADDING
    max_columns = max(1, center_panel_width // stride)
    start_x = center_panel_x + SELECTION_ICON_PADDING
    start_y = screen_height - BOTTOM_MENU_HEIGHT + SELECTION_ICON_PADDING
    rects: list[pygame.Rect] = []
    for index in range(selection_count):
        column = index % max_columns
        row = index // max_columns
        x = start_x + column * stride
        y = start_y + row * stride
        if y + SELECTION_ICON_SIZE > screen_height:
            break
        rects.append(pygame.Rect(x, y, SELECTION_ICON_SIZE, SELECTION_ICON_SIZE))
    return SelectionPanelLayout(center_panel_x, center_panel_width, portrait_x, tuple(rects))
