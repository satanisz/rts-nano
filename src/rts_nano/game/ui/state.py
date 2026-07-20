"""Transient state shared by Pygame input and rendering adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from rts_nano.game.ui.command_panel import CommandPanel

if TYPE_CHECKING:
    from rts_nano.game.ui.effects import ClickMarker


@dataclass(slots=True)
class PresentationState:
    """Own UI-only objects that must never enter simulation state."""

    command_panel: CommandPanel = field(default_factory=CommandPanel)
    click_markers: list[ClickMarker] = field(default_factory=list)
    tech_tree_visible: bool = False

    def reset_match(self) -> None:
        """Discard transient objects while retaining reusable UI helpers."""
        self.click_markers.clear()
        self.tech_tree_visible = False
