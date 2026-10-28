"""Transient state shared by Pygame input and rendering adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from rts_nano.game.ui.command_panel import CommandPanel
from rts_nano.game.ui.match_view import MatchView

if TYPE_CHECKING:
    from rts_nano.game.ui.effects import ClickMarker


@dataclass(slots=True)
class PresentationState:
    """Own UI-only objects that must never enter simulation state."""

    command_panel: CommandPanel = field(default_factory=CommandPanel)
    click_markers: list[ClickMarker] = field(default_factory=list)
    tech_tree_visible: bool = False
    view: MatchView = field(default_factory=MatchView)

    def reset_match(self) -> None:
        """Discard transient objects while retaining reusable UI helpers."""
        self.click_markers.clear()
        self.tech_tree_visible = False
        self.command_panel.reset()
        self.view.reset()
