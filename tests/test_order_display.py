"""Tests for player-facing active and queued order labels."""

from rts_nano.game.order import Order
from rts_nano.game.ui.order_display import format_order, unit_order_lines
from rts_nano.simulation.entities.base import TeamColor
from rts_nano.simulation.entities.units import Peasant


def test_order_labels_use_english_content_names() -> None:
    assert format_order(Order("build", target_content_id="house")) == "Build House"
    assert format_order(Order("gather", target_content_id="wood")) == "Gather Wood"


def test_unit_order_lines_show_active_build_and_queued_gather() -> None:
    peasant = Peasant(0, 0, TeamColor.BLUE)
    peasant.state = "BUILDING"
    peasant.current_order = Order("build", (40, 40), target_content_id="house")
    peasant.order_queue.append(Order("gather", (80, 80), target_content_id="wood"))

    assert unit_order_lines(peasant) == ["Order: Build House", "Queue: Gather Wood"]
